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
    """
    Single bot that handles ALL functions:
    - Email processing
    - Job matching
    - Reply management
    - Professor outreach
    """

    def __init__(self):
        print("🤖 Initializing AI Personal Assistant...")
        self.gmail = GmailClient()
        self.telegram = TelegramBot()
        self.professor_handler = ProfessorTelegramHandler(self.gmail.service)
        self.db = Database()

        # Email reply tracking
        self.pending_email_replies = {}

        print("✅ All modules ready!")

    def start(self):
        """Start the unified bot."""
        self.telegram.send_message(START_MESSAGE)
        print("🤖 Bot is running. Listening for Telegram commands...")
        print("Press CTRL+C to stop.")

        # Start email auto-check in background
        email_thread = threading.Thread(
            target=self._auto_email_check,
            daemon=True
        )
        email_thread.start()

        # Main loop - listen for Telegram messages
        while True:
            try:
                updates = self.telegram.get_updates()

                for update in updates:
                    message = update.get("message", {})
                    text = message.get("text", "").strip()
                    chat_id = str(message.get("chat", {}).get("id", ""))

                    if chat_id == str(settings.TELEGRAM_CHAT_ID) and text:
                        print(f"📩 Received: {text[:80]}")
                        self._handle_command(text)

                time.sleep(3)

            except KeyboardInterrupt:
                print("\n👋 Bot stopped.")
                break
            except Exception as e:
                logger.error(f"Bot error: {e}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(5)

    def _handle_command(self, text: str):
        """Route command to the right handler."""
        upper = text.upper().strip()

        # START / HELP
        if upper == "START" or upper == "/START":
            self.telegram.send_message(START_MESSAGE)
            return

        if upper == "HELP" or upper == "/HELP":
            self.telegram.send_message(HELP_MESSAGE)
            return

        # CHECK - process emails now
        if upper == "CHECK":
            self._handle_check()
            return

        # JOBS - show recent job matches
        if upper == "JOBS":
            self._handle_jobs()
            return

        # REPLIES - show pending replies
        if upper == "REPLIES":
            self._handle_replies()
            return

        # STATUS - daily stats
        if upper == "STATUS":
            self._handle_status()
            return

        # Professor outreach commands
        if self.professor_handler.handle_message(
            text,
            send_func=self.telegram.send_message
        ):
            return

        # YES/NO/EDIT for email replies
        if upper == "YES" and self.pending_email_replies:
            self._handle_email_yes()
            return

        if upper == "NO" and self.pending_email_replies:
            self._handle_email_no()
            return

        if upper.startswith("EDIT:") and self.pending_email_replies:
            self._handle_email_edit(text[5:].strip())
            return

        # Unknown command
        self.telegram.send_message(
            "Unknown command. Type START for all options."
        )

    def _handle_check(self):
        """Process emails now."""
        self.telegram.send_message("🔄 Processing emails now...")

        try:
            orchestrator = EmailAssistantOrchestrator()
            stats = orchestrator.run(max_emails=10, query="in:inbox")

            self.telegram.send_message(
                f"✅ Email check complete!\n\n"
                f"Processed: {stats['total']}\n"
                f"Jobs found: {stats['job_emails']}\n"
                f"Strong matches: {stats['strong_matches']}\n"
                f"Replies pending: {stats['replies_generated']}"
            )

        except Exception as e:
            self.telegram.send_message(f"❌ Error: {e}")

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
                self.telegram.send_message("No job matches yet. Type CHECK to process emails.")
                return

            msg = "💼 RECENT JOB MATCHES:\n\n"
            for m in matches:
                score = f"{m.match_score:.0%}" if m.match_score else "N/A"
                emoji = "🟢" if m.match_score and m.match_score >= 0.8 else "🟡"
                applied = "✅" if m.applied else "❌"
                msg += (
                    f"{emoji} {m.job_title}\n"
                    f"   at {m.company}\n"
                    f"   Score: {score} | Applied: {applied}\n\n"
                )

            self.telegram.send_message(msg)

        except Exception as e:
            self.telegram.send_message(f"Error loading jobs: {e}")

    def _handle_replies(self):
        """Show pending reply drafts."""
        try:
            from src.utils.database import ReplyDraft as RD
            session = self.db.Session()
            drafts = session.query(RD).filter_by(
                is_sent=False
            ).order_by(RD.created_at.desc()).limit(5).all()
            session.close()

            if not drafts:
                self.telegram.send_message("No pending replies.")
                return

            msg = "✍️ PENDING REPLIES:\n\n"
            for d in drafts:
                email = self.db.get_email(d.email_id)
                subject = email.get("subject", "Unknown") if email else "Unknown"
                msg += (
                    f"- Re: {subject[:50]}\n"
                    f"  Confidence: {d.confidence:.0%}\n\n"
                )

            msg += "View and send from dashboard: localhost:8503"
            self.telegram.send_message(msg)

        except Exception as e:
            self.telegram.send_message(f"Error loading replies: {e}")

    def _handle_status(self):
        """Show daily stats."""
        try:
            stats = self.db.get_daily_stats()

            # Professor outreach stats
            import sqlite3
            conn = sqlite3.connect("data/assistant.db")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM professor_outreach WHERE status='sent'"
            )
            prof_sent = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM professor_outreach WHERE status='pending'"
            )
            prof_pending = cursor.fetchone()[0]
            conn.close()

            msg = f"""📊 TODAY'S STATS:

📧 Emails processed: {stats['total_processed']}
💼 Job opportunities: {stats['job_emails']}
✍️ Replies pending: {stats['replies_pending']}
📤 Replies sent: {stats['replies_sent']}
📝 Applications: {stats['applications']}

🎓 Professor outreach sent: {prof_sent}
🎓 Professor outreach pending: {prof_pending}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}
📊 Dashboard: localhost:8503"""

            self.telegram.send_message(msg)

        except Exception as e:
            self.telegram.send_message(f"Error: {e}")

    def _handle_email_yes(self):
        """Send most recent pending email reply."""
        if not self.pending_email_replies:
            self.telegram.send_message("No pending email replies.")
            return

        email_id = list(self.pending_email_replies.keys())[-1]
        pending = self.pending_email_replies[email_id]

        success = self.gmail.send_email(
            to=pending['to'],
            subject=pending['subject'],
            body=pending['body'],
            thread_id=pending.get('thread_id', '')
        )

        if success:
            self.db.mark_reply_sent(email_id)
            del self.pending_email_replies[email_id]
            self.telegram.send_message(f"✅ Reply sent to {pending['to']}")
        else:
            self.telegram.send_message("❌ Failed to send.")

    def _handle_email_no(self):
        """Discard most recent pending reply."""
        if self.pending_email_replies:
            email_id = list(self.pending_email_replies.keys())[-1]
            del self.pending_email_replies[email_id]
            self.telegram.send_message("❌ Reply discarded.")

    def _handle_email_edit(self, new_body: str):
        """Edit and send email reply."""
        if not new_body:
            self.telegram.send_message("Provide text after EDIT:")
            return

        if not self.pending_email_replies:
            self.telegram.send_message("No pending email replies.")
            return

        email_id = list(self.pending_email_replies.keys())[-1]
        pending = self.pending_email_replies[email_id]

        full_body = new_body + "\n\n" + settings.EMAIL_SIGNATURE

        success = self.gmail.send_email(
            to=pending['to'],
            subject=pending['subject'],
            body=full_body,
            thread_id=pending.get('thread_id', '')
        )

        if success:
            self.db.mark_reply_sent(email_id)
            del self.pending_email_replies[email_id]
            self.telegram.send_message(f"✅ Edited reply sent to {pending['to']}")
        else:
            self.telegram.send_message("❌ Failed to send.")

    def _auto_email_check(self):
        """Background thread that checks emails periodically."""
        interval = settings.EMAIL_CHECK_INTERVAL_MINUTES * 60

        while True:
            try:
                time.sleep(interval)
                print(f"⏰ Auto email check at {datetime.now().strftime('%H:%M')}")
                self._handle_check()
            except Exception as e:
                logger.error(f"Auto check error: {e}")
                time.sleep(60)


if __name__ == "__main__":
    bot = UnifiedBot()
    bot.start()
