from typing import Dict, Any, List
from datetime import datetime
from src.email_reader.gmail_client import GmailClient
from src.classifier.importance_classifier import EmailClassifier
from src.cv_parser.cv_extractor import CVExtractor
from src.job_matcher.matcher import JobMatcher
from src.auto_replier.reply_generator import ReplyGenerator
from src.auto_applier.cover_letter import CoverLetterGenerator
from src.utils.firebase_db import FirebaseDatabase as Database
from src.utils.logger import get_logger
from src.utils.telegram_bot import TelegramBot
from src.utils.link_extractor import extract_all_important_links
from config.settings import settings

logger = get_logger(__name__)


class EmailAssistantOrchestrator:
    def __init__(self):
        logger.info("Initializing AI Email Assistant...")
        self.gmail = GmailClient()
        self.classifier = EmailClassifier()
        self.cv_extractor = CVExtractor()
        self.job_matcher = JobMatcher()
        self.reply_generator = ReplyGenerator()
        self.cover_letter_gen = CoverLetterGenerator()
        self.db = Database()
        self.telegram = TelegramBot()
        logger.info("All modules initialized ✅")

    def run(self, max_emails: int = 20, query: str = "is:unread"):
        """Run the full email processing pipeline."""
        logger.info("=" * 60)
        logger.info(f"Starting email processing at {datetime.now().strftime('%H:%M:%S')}")
        logger.info("=" * 60)

        stats = {
            'total': 0, 'job_emails': 0, 'strong_matches': 0,
            'replies_generated': 0, 'cover_letters': 0, 'errors': 0
        }

        # Fetch emails
        logger.info(f"Fetching emails (query: {query})...")
        emails = self.gmail.fetch_emails(max_results=max_emails, query=query)

        if not emails:
            logger.info("No emails found.")
            self.telegram.send_message("📭 No new emails found.")
            return stats

        stats['total'] = len(emails)
        logger.info(f"Found {len(emails)} emails to process")
        self.telegram.send_message(
            f"🤖 *Processing {len(emails)} emails...*\nI'll send you each one shortly."
        )

        self.db.store_emails(emails)

        # Skip already processed emails
        processed_ids = self.get_processed_email_ids()
        emails = [e for e in emails if e['id'] not in processed_ids]
        
        if not emails:
            logger.info("All emails already processed. Nothing new.")
            self.telegram.send_message("📭 No new emails to process.")
            return stats

        logger.info(f"New emails to process: {len(emails)}")
        stats['total'] = len(emails)

        for i, email in enumerate(emails, 1):
            logger.info(f"\n{'='*40}")
            logger.info(f"Email {i}/{len(emails)}: {email['subject'][:60]}")

            try:
                # Step 1: Classify
                classification = self.classifier.classify(email)
                self.db.update_email_classification(
                    email['id'], classification.model_dump()
                )

                # Step 2: Add Gmail label
                label_map = {
                    'critical': 'AI-Assistant/Critical',
                    'high': 'AI-Assistant/High',
                    'medium': 'AI-Assistant/Medium',
                    'low': 'AI-Assistant/Low',
                    'ignore': 'AI-Assistant/Ignore'
                }
                self.gmail.add_label(
                    email['id'],
                    label_map.get(classification.importance, 'AI-Assistant/Medium')
                )

                logger.info(
                    f"Category: {classification.category} | "
                    f"Importance: {classification.importance} | "
                    f"Job: {classification.is_job_related}"
                )

                # Step 3: Extract links
                link_data = extract_all_important_links(email)
                apply_link = link_data.get('apply_link', '')

                # Step 4: Handle based on category
                if classification.is_job_related:
                    stats['job_emails'] += 1
                    self._handle_job_email(
                        email, classification, apply_link, stats
                    )

                elif classification.needs_reply:
                    self._handle_reply_email(
                        email, classification, stats
                    )

                else:
                    # Info only - send summary to Telegram
                    self._handle_info_email(email, classification)

                # Wait between emails to avoid spam
                if i < len(emails):
                    import time
                    time.sleep(2)

            except Exception as e:
                stats['errors'] += 1
                logger.error(f"Error processing email {i}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue

        # Final summary
        summary = f"""🤖 *Email Processing Complete!*

📊 *Results:*
• Total processed: {stats['total']}
• Job opportunities: {stats['job_emails']}
• Strong matches: {stats['strong_matches']}
• Replies pending your approval: {stats['replies_generated']}
• Cover letters generated: {stats['cover_letters']}
• Errors: {stats['errors']}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}
📊 View details: Dashboard at localhost:8503"""

        self.telegram.send_message(summary)

        logger.info(f"\nDone! Stats: {stats}")
        return stats

    def _handle_job_email(
        self,
        email: Dict,
        classification: Any,
        apply_link: str,
        stats: Dict
    ):
        """Handle a job-related email."""
        logger.info("  📋 Job email - analyzing match...")

        body = email.get('body_text') or email.get('snippet', '')

        # Match against profile
        match = self.job_matcher.match_job(body)
        self.db.store_job_match(email['id'], match.model_dump())

        if match.recommendation in ['STRONG_APPLY', 'APPLY']:
            stats['strong_matches'] += 1

            # Generate cover letter
            logger.info("  📝 Generating cover letter...")
            cover_letter = self.cover_letter_gen.generate(body, match)
            self.db.store_cover_letter(email['id'], cover_letter)
            stats['cover_letters'] += 1

            # Generate reply
            logger.info("  ✉️ Generating job interest reply...")
            reply = self.reply_generator.generate_job_reply(email, match)
            self.db.store_reply_draft(email['id'], reply.model_dump())
            stats['replies_generated'] += 1

            # Build summary
            summary = f"""*Job:* {match.job_title} at {match.company}
*Match Score:* {match.overall_match_score:.0%} ({match.recommendation})
*Matching Skills:* {', '.join(match.matching_skills[:5])}
*Missing Skills:* {', '.join(match.missing_skills[:3]) if match.missing_skills else 'None'}
*Reasoning:* {match.reasoning}"""

            # Send to Telegram with reply for approval
            self.telegram.send_email_notification(
                email_data=email,
                summary=summary,
                reply_draft=reply.body,
                apply_link=apply_link,
                is_job=True,
                email_id=email['id']
            )

            logger.info(
                f"  ✅ {match.overall_match_score:.0%} match | "
                f"{match.job_title} at {match.company}"
            )

        else:
            # Low match - just notify, no reply
            summary = f"""*Job:* {match.job_title} at {match.company}
*Match Score:* {match.overall_match_score:.0%} ({match.recommendation})
*Reasoning:* {match.reasoning}
_Below your match threshold - no reply generated_"""

            self.telegram.send_info_notification(
                email_data=email,
                summary=summary,
                category='job_opportunity'
            )
            logger.info(f"  ⏭️ Low match: {match.overall_match_score:.0%}")

    def _handle_reply_email(
        self,
        email: Dict,
        classification: Any,
        stats: Dict
    ):
        """Handle email that needs a reply."""
        logger.info("  💬 Generating reply...")

        reply = self.reply_generator.generate_reply(
            email, classification.model_dump()
        )
        self.db.store_reply_draft(email['id'], reply.model_dump())
        stats['replies_generated'] += 1

        summary = classification.summary or "This email requires your response."

        # Send to Telegram for approval
        self.telegram.send_email_notification(
            email_data=email,
            summary=summary,
            reply_draft=reply.body,
            apply_link='',
            is_job=False,
            email_id=email['id']
        )

        logger.info(f"  ✅ Reply draft sent to Telegram for approval")

    def _handle_info_email(self, email: Dict, classification: Any):
        """Handle informational email - just notify."""
        logger.info("  ℹ️ Info email - sending summary only")

        summary = classification.summary or "Informational email, no action needed."

        self.telegram.send_info_notification(
            email_data=email,
            summary=summary,
            category=classification.category
        )

    def process_single_email(self, email_id: str) -> Dict[str, Any]:
        """Process a single email by ID."""
        email = self.db.get_email(email_id)
        if not email:
            return {"error": "Email not found"}

        classification = self.classifier.classify(email)
        result = {"classification": classification.model_dump()}

        if classification.is_job_related:
            body = email.get('body_text') or email.get('snippet', '')
            match = self.job_matcher.match_job(body)
            result["job_match"] = match.model_dump()

        if classification.needs_reply:
            reply = self.reply_generator.generate_reply(
                email, classification.model_dump()
            )
            result["reply_draft"] = reply.model_dump()

        return result

    def start_reply_listener(self, timeout: int = 600):
        """
        Start listening for YES/NO/EDIT replies on Telegram.
        Call this after run() to handle approvals.
        """
        logger.info("Starting Telegram reply listener...")

        def send_email(to, subject, body, thread_id=''):
            return self.gmail.send_email(
                to=to,
                subject=subject,
                body=body,
                thread_id=thread_id
            )

        self.telegram.listen_for_replies(
            send_email_func=send_email,
            timeout_seconds=timeout
        )


    def get_processed_email_ids(self) -> set:
        """Get IDs of already processed emails from Firebase."""
        try:
            docs = self.db.db.collection("emails")                .where("is_processed", "==", True)                .stream()
            return {doc.id for doc in docs}
        except Exception as e:
            return set()
