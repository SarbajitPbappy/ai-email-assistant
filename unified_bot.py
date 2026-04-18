import time
import threading
from datetime import datetime
from src.email_reader.gmail_client import GmailClient
from src.agent.orchestrator import EmailAssistantOrchestrator
from src.professor_outreach.telegram_handler import ProfessorTelegramHandler
from src.utils.telegram_bot import TelegramBot
from src.utils.telegram_commands import START_MESSAGE, HELP_MESSAGE
from src.utils.database import Database
from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class UnifiedBot:
    def __init__(self):
        print("🤖 Initializing AI Personal Assistant...")
        self.gmail = GmailClient()
        self.telegram = TelegramBot()
        self.professor_handler = ProfessorTelegramHandler(self.gmail.service)
        self.db = Database()

        # Reply queue - list of pending replies
        self.reply_queue = []
        self.current_reply = None

        print("✅ All modules ready!")

    def start(self):
        """Start the unified bot."""
        self.telegram.send_message(START_MESSAGE)
        print("🤖 Bot is running. Listening for Telegram commands...")
        print("Press CTRL+C to stop.")

        # Start auto email check in background
        email_thread = threading.Thread(
            target=self._auto_email_check,
            daemon=True
        )
        email_thread.start()

        # Main loop
        while True:
            try:
                updates = self.telegram.get_updates()
                for update in updates:
                    message = update.get("message", {})
                    text = message.get("text", "").strip()
                    chat_id = str(message.get("chat", {}).get("id", ""))

                    if chat_id == str(settings.TELEGRAM_CHAT_ID) and text:
                        print(f"📩 Received: {text[:60]}")
                        self._handle_command(text)

                time.sleep(3)

            except KeyboardInterrupt:
                print("\n👋 Bot stopped.")
                break
            except Exception as e:
                logger.error(f"Bot error: {e}")
                time.sleep(5)

    def _handle_command(self, text: str):
        """Route command to correct handler."""
        upper = text.upper().strip()

        # START / HELP
        if upper in ["START", "/START"]:
            self.telegram.send_message(START_MESSAGE)
            return

        if upper in ["HELP", "/HELP"]:
            self.telegram.send_message(HELP_MESSAGE)
            return

        # CHECK
        if upper == "CHECK":
            self._handle_check()
            return

        # JOBS
        if upper == "JOBS":
            self._handle_jobs()
            return

        # REPLIES
        if upper == "REPLIES":
            self._handle_show_replies()
            return

        # STATUS
        if upper == "STATUS":
            self._handle_status()
            return

        # SKIP - skip current reply in queue
        if upper == "SKIP":
            self._handle_skip()
            return

        # YES - approve current reply
        if upper == "YES" and self.current_reply:
            self._handle_yes()
            return

        # NO - discard current reply
        if upper == "NO" and self.current_reply:
            self._handle_no()
            return

        # EDIT:
        if upper.startswith("EDIT:") and self.current_reply:
            self._handle_edit(text[5:].strip())
            return

        # Professor commands
        if self.professor_handler.handle_message(
            text,
            send_func=self.telegram.send_message
        ):
            return

        # Unknown
        self.telegram.send_message(
            "Unknown command.\n"
            "Type START to see all options."
        )

    def _handle_check(self):
        """Process new emails."""
        self.telegram.send_message("🔄 Checking for new emails...")
        try:
            orchestrator = EmailAssistantOrchestrator()
            orchestrator.telegram = self.telegram

            # Override the telegram notification in orchestrator
            # to add replies to our queue instead
            original_send = orchestrator._handle_reply_email

            def queued_reply_handler(email, classification, stats):
                """Add reply to queue instead of sending directly."""
                from src.auto_replier.reply_generator import ReplyGenerator
                gen = ReplyGenerator()
                reply = gen.generate_reply(email, classification.model_dump())
                self.db.store_reply_draft(email['id'], reply.model_dump())
                stats['replies_generated'] += 1

                # Add to queue
                self.reply_queue.append({
                    'email_id': email['id'],
                    'email': email,
                    'reply': reply,
                    'type': 'email'
                })
                logger.info(f"Added to reply queue: {email['subject'][:40]}")

            orchestrator._handle_reply_email = queued_reply_handler

            stats = orchestrator.run(max_emails=10, query="in:inbox")

            msg = (
                f"Email check complete!\n\n"
                f"Processed: {stats['total']}\n"
                f"New jobs: {stats['job_emails']}\n"
                f"Strong matches: {stats['strong_matches']}\n"
                f"Replies queued: {len(self.reply_queue)}"
            )
            self.telegram.send_message(msg)

            # Show first pending reply if any
            if self.reply_queue and not self.current_reply:
                self._show_next_reply()

        except Exception as e:
            logger.error(f"Check error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.telegram.send_message(f"Error: {e}")

    def _show_next_reply(self):
        """Show the next reply in queue for approval."""
        if not self.reply_queue:
            self.telegram.send_message(
                "All replies processed!\n"
                "Check dashboard for job cover letters."
            )
            self.current_reply = None
            return

        self.current_reply = self.reply_queue.pop(0)
        email = self.current_reply['email']
        reply = self.current_reply['reply']

        remaining = len(self.reply_queue)
        remaining_text = f"\n({remaining} more in queue)" if remaining > 0 else ""

        msg = (
            f"REPLY APPROVAL NEEDED{remaining_text}\n\n"
            f"To: {email.get('from', 'Unknown')[:60]}\n"
            f"Subject: {email.get('subject', 'No Subject')[:80]}\n\n"
            f"GENERATED REPLY:\n"
            f"------------------\n"
            f"{reply.body[:800]}\n"
            f"------------------\n\n"
            f"YES - Send this reply\n"
            f"NO - Discard\n"
            f"EDIT: <text> - Edit and send\n"
            f"SKIP - Skip for now"
        )
        self.telegram.send_message(msg)

    def _handle_yes(self):
        """Send current reply."""
        if not self.current_reply:
            self.telegram.send_message("No pending reply.")
            return

        email = self.current_reply['email']
        reply = self.current_reply['reply']

        success = self.gmail.send_email(
            to=email.get('from', ''),
            subject=reply.subject,
            body=reply.body,
            thread_id=email.get('thread_id', '')
        )

        if success:
            self.db.mark_reply_sent(self.current_reply['email_id'])
            self.telegram.send_message(
                f"Reply sent to {email.get('from', '')[:50]}"
            )
        else:
            self.telegram.send_message("Failed to send reply.")

        self.current_reply = None

        # Show next in queue
        time.sleep(1)
        if self.reply_queue:
            self._show_next_reply()
        else:
            self.telegram.send_message(
                "All replies processed!"
            )

    def _handle_no(self):
        """Discard current reply."""
        if not self.current_reply:
            self.telegram.send_message("No pending reply.")
            return

        subject = self.current_reply['email'].get('subject', '')[:40]
        self.current_reply = None
        self.telegram.send_message(f"Reply discarded: {subject}")

        # Show next
        time.sleep(1)
        if self.reply_queue:
            self._show_next_reply()
        else:
            self.telegram.send_message("Queue empty!")

    def _handle_edit(self, new_body: str):
        """Edit and send current reply."""
        if not self.current_reply or not new_body:
            self.telegram.send_message(
                "No pending reply or empty edit text."
            )
            return

        email = self.current_reply['email']
        reply = self.current_reply['reply']
        full_body = new_body + "\n\n" + settings.EMAIL_SIGNATURE

        success = self.gmail.send_email(
            to=email.get('from', ''),
            subject=reply.subject,
            body=full_body,
            thread_id=email.get('thread_id', '')
        )

        if success:
            self.db.mark_reply_sent(self.current_reply['email_id'])
            self.telegram.send_message("Edited reply sent!")
        else:
            self.telegram.send_message("Failed to send.")

        self.current_reply = None
        time.sleep(1)

        if self.reply_queue:
            self._show_next_reply()

    def _handle_skip(self):
        """Skip current reply - put back in queue end."""
        if not self.current_reply:
            self.telegram.send_message("Nothing to skip.")
            return

        # Put at end of queue
        self.reply_queue.append(self.current_reply)
        self.current_reply = None
        self.telegram.send_message("Skipped. Showing next...")

        time.sleep(1)
        self._show_next_reply()

    def _handle_show_replies(self):
        """Show pending replies count."""
        pending = len(self.reply_queue)
        current = "Yes" if self.current_reply else "No"

        msg = (
            f"REPLY QUEUE:\n\n"
            f"Currently showing: {current}\n"
            f"Waiting in queue: {pending}\n\n"
        )

        if pending > 0:
            msg += "Queued replies:\n"
            for i, r in enumerate(self.reply_queue[:5], 1):
                subj = r['email'].get('subject', 'No Subject')[:40]
                msg += f"{i}. {subj}\n"

        if not self.current_reply and pending > 0:
            msg += "\nType REPLIES to start reviewing."

        self.telegram.send_message(msg)

        # If nothing currently showing, show first
        if not self.current_reply and self.reply_queue:
            self._show_next_reply()

    def _handle_jobs(self):
        """Show recent job matches."""
        try:
            from src.utils.database import JobMatch
            session = self.db.Session()
            matches = session.query(JobMatch).order_by(
                JobMatch.created_at.desc()
            ).limit(5).all()
            session.close()

            if not matches:
                self.telegram.send_message(
                    "No job matches yet.\nType CHECK to process emails."
                )
                return

            msg = "RECENT JOB MATCHES:\n\n"
            for m in matches:
                score = f"{m.match_score:.0%}" if m.match_score else "N/A"
                emoji = "🟢" if m.match_score and m.match_score >= 0.8 else "🟡"
                applied = "Applied" if m.applied else "Not Applied"
                msg += (
                    f"{emoji} {m.job_title}\n"
                    f"   Company: {m.company}\n"
                    f"   Score: {score} | {applied}\n\n"
                )

            msg += "View cover letters at dashboard: localhost:8503"
            self.telegram.send_message(msg)

        except Exception as e:
            self.telegram.send_message(f"Error: {e}")

    def _handle_status(self):
        """Show daily stats."""
        try:
            import sqlite3
            stats = self.db.get_daily_stats()
            conn = sqlite3.connect("data/assistant.db")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM professor_outreach WHERE status='sent'"
            )
            prof_sent = cursor.fetchone()[0]
            conn.close()

            msg = (
                f"TODAY'S STATS:\n\n"
                f"Emails processed: {stats['total_processed']}\n"
                f"Job opportunities: {stats['job_emails']}\n"
                f"Replies pending: {stats['replies_pending']}\n"
                f"Replies sent: {stats['replies_sent']}\n"
                f"Professors contacted: {prof_sent}\n"
                f"Queue: {len(self.reply_queue)} waiting\n\n"
                f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            self.telegram.send_message(msg)

        except Exception as e:
            self.telegram.send_message(f"Error: {e}")

    def _auto_email_check(self):
        """Background auto check."""
        interval = settings.EMAIL_CHECK_INTERVAL_MINUTES * 60
        while True:
            try:
                time.sleep(interval)
                print(f"Auto check at {datetime.now().strftime('%H:%M')}")
                self._handle_check()
            except Exception as e:
                logger.error(f"Auto check error: {e}")
                time.sleep(60)


if __name__ == "__main__":
    bot = UnifiedBot()
    bot.start()
