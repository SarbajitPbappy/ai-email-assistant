import requests
import json
import time
from typing import Dict, Any, Optional, Callable
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


def escape_telegram(text: str) -> str:
    """Remove special markdown characters to avoid parse errors."""
    if not text:
        return ""
    # Just remove problematic characters instead of escaping
    for char in ['*', '_', '`', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(char, ' ')
    # Clean up multiple spaces
    import re
    text = re.sub(r' +', ' ', text)
    return text.strip()


class TelegramBot:
    """Telegram bot that sends notifications and handles YES/NO/EDIT replies."""

    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0
        self.pending_approvals: Dict[str, Dict] = {}

    def send_message(self, text: str) -> Optional[int]:
        """Send a plain text message and return message ID."""
        try:
            if len(text) > 4096:
                text = text[:4090] + "\n...[truncated]"

            response = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "disable_web_page_preview": True
                },
                timeout=10
            )

            if response.status_code == 200:
                msg_id = response.json()['result']['message_id']
                logger.info(f"Telegram message sent (ID: {msg_id})")
                return msg_id
            else:
                logger.error(f"Telegram error: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return None

    def send_email_notification(
        self,
        email_data: Dict[str, Any],
        summary: str,
        reply_draft: str,
        apply_link: str = "",
        is_job: bool = False,
        email_id: str = ""
    ) -> Optional[int]:
        """Send full email notification to Telegram."""

        job_badge = "💼 JOB OPPORTUNITY" if is_job else "📧 NEW EMAIL"
        
        # Clean all text
        from_clean = escape_telegram(email_data.get('from', 'Unknown'))[:80]
        subject_clean = escape_telegram(email_data.get('subject', 'No Subject'))[:100]
        summary_clean = escape_telegram(summary)[:500]
        reply_clean = reply_draft[:800] if reply_draft else ""

        link_section = f"\n🔗 Apply Link:\n{apply_link}\n" if apply_link else ""

        message = f"""{job_badge}

From: {from_clean}
Subject: {subject_clean}

SUMMARY:
{summary_clean}
{link_section}
GENERATED REPLY:
------------------
{reply_clean}
------------------

Reply with:
YES - Send this reply as is
NO - Discard this reply
EDIT: <your new text> - Replace body and send

Email ID: {email_id}"""

        msg_id = self.send_message(message)

        if email_id and msg_id:
            self.pending_approvals[email_id] = {
                'email_data': email_data,
                'reply_draft': reply_draft,
                'msg_id': msg_id,
                'status': 'pending'
            }

        return msg_id

    def send_info_notification(
        self,
        email_data: Dict[str, Any],
        summary: str,
        category: str
    ):
        """Send info-only notification."""
        category_icons = {
            'newsletter': '📰',
            'promotional': '🛍️',
            'spam': '🚫',
            'personal': '👤',
            'job_opportunity': '💼',
            'other': '📌'
        }
        icon = category_icons.get(category, '📌')

        from_clean = escape_telegram(email_data.get('from', 'Unknown'))[:80]
        subject_clean = escape_telegram(email_data.get('subject', 'No Subject'))[:100]
        summary_clean = escape_telegram(summary)[:400]

        message = f"""{icon} {category.upper()}

From: {from_clean}
Subject: {subject_clean}

Summary:
{summary_clean}

No reply needed."""

        self.send_message(message)

    def get_updates(self) -> list:
        """Get new messages from Telegram."""
        try:
            response = requests.get(
                f"{self.base_url}/getUpdates",
                params={
                    "offset": self.last_update_id + 1,
                    "timeout": 5,
                    "limit": 10
                },
                timeout=10
            )

            if response.status_code == 200:
                updates = response.json().get('result', [])
                if updates:
                    self.last_update_id = updates[-1]['update_id']
                return updates
            return []

        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return []

    def process_reply(
        self,
        text: str,
        send_email_func: Callable
    ) -> str:
        """Process YES/NO/EDIT reply from user."""
        text = text.strip()
        upper_text = text.upper()

        if not self.pending_approvals:
            return "No pending emails to approve."

        # Get most recent pending email
        pending_email_id = None
        for eid, data in self.pending_approvals.items():
            if data['status'] == 'pending':
                pending_email_id = eid

        if not pending_email_id:
            return "No pending emails found."

        pending = self.pending_approvals[pending_email_id]
        email_data = pending['email_data']
        subject = email_data.get('subject', 'No Subject')
        to_address = email_data.get('from', '')

        # Handle YES
        if upper_text == 'YES':
            reply_body = pending['reply_draft']
            success = send_email_func(
                to=to_address,
                subject=f"Re: {subject}",
                body=reply_body,
                thread_id=email_data.get('thread_id', '')
            )
            if success:
                self.pending_approvals[pending_email_id]['status'] = 'sent'
                return f"✅ Reply sent to {to_address}"
            else:
                return "❌ Failed to send reply"

        # Handle NO
        elif upper_text == 'NO':
            self.pending_approvals[pending_email_id]['status'] = 'discarded'
            return f"❌ Reply discarded for: {subject[:50]}"

        # Handle EDIT
        elif upper_text.startswith('EDIT:'):
            new_body = text[5:].strip()
            if not new_body:
                return "Please provide text after EDIT:"

            full_body = f"{new_body}\n\n{settings.EMAIL_SIGNATURE}"
            success = send_email_func(
                to=to_address,
                subject=f"Re: {subject}",
                body=full_body,
                thread_id=email_data.get('thread_id', '')
            )
            if success:
                self.pending_approvals[pending_email_id]['status'] = 'sent'
                return f"✅ Edited reply sent to {to_address}"
            else:
                return "❌ Failed to send edited reply"

        else:
            return "Please reply with:\nYES - send\nNO - discard\nEDIT: <your text> - edit and send"

    def listen_for_replies(
        self,
        send_email_func: Callable,
        timeout_seconds: int = 300
    ):
        """Listen for YES/NO/EDIT replies."""
        logger.info(f"Listening for Telegram replies ({timeout_seconds}s)...")
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            updates = self.get_updates()

            for update in updates:
                message = update.get('message', {})
                text = message.get('text', '').strip()
                chat_id = str(message.get('chat', {}).get('id', ''))

                if chat_id == str(self.chat_id) and text:
                    logger.info(f"Received: {text[:50]}")
                    result = self.process_reply(text, send_email_func)
                    self.send_message(result)
                    logger.info(f"Processed: {result}")

            time.sleep(3)

        pending_count = sum(
            1 for d in self.pending_approvals.values()
            if d['status'] == 'pending'
        )
        if pending_count > 0:
            self.send_message(
                f"⏰ Listening timeout reached.\n"
                f"{pending_count} replies still pending.\n"
                f"Use dashboard to review: localhost:8503"
            )

        logger.info("Stopped listening for replies")


    def process_professor_command(
        self,
        text: str,
        outreach_manager
    ) -> str:
        """
        Handle professor outreach commands from Telegram.

        Commands:
        PHD <url or text>     - Start PhD outreach
        MASTERS <url or text> - Start Masters outreach
        YES                   - Send pending professor email
        NO                    - Discard pending professor email
        EDIT: <text>          - Edit and send
        PROF_EMAIL: <email>   - Set professor email manually
        STATUS                - Show all outreach history
        """
        text = text.strip()
        upper = text.upper()

        # PHD or MASTERS command
        if upper.startswith('PHD ') or upper.startswith('MASTERS '):
            parts = text.split(' ', 1)
            app_type = parts[0].upper()
            content = parts[1].strip() if len(parts) > 1 else ''

            if not content:
                return "Please provide a URL or professor summary after PHD/MASTERS"

            self.send_message(
                f"🔍 Analyzing professor profile for {app_type} application...\n"
                f"This may take 1-2 minutes."
            )

            try:
                result = outreach_manager.process_professor_request(
                    content, app_type
                )

                # Store pending
                outreach_id = result['outreach_id']
                self.pending_professor_emails = getattr(
                    self, 'pending_professor_emails', {}
                )
                self.pending_professor_emails[str(outreach_id)] = result
                self.last_outreach_id = outreach_id

                # Send notification
                message = outreach_manager.build_telegram_message(result)
                self.send_message(message)

                return f"Professor analysis complete! Outreach ID: {outreach_id}"

            except Exception as e:
                return f"Error analyzing professor: {e}"

        # YES - Send professor email
        elif upper == 'YES' and hasattr(self, 'last_outreach_id'):
            outreach_id = self.last_outreach_id
            success = outreach_manager.send_professor_email(outreach_id)
            if success:
                return "✅ Email sent to professor with CV and Transcript attached!"
            else:
                return "❌ Failed to send. Check if professor email is set correctly."

        # NO - Discard
        elif upper == 'NO' and hasattr(self, 'last_outreach_id'):
            return "❌ Professor email discarded."

        # EDIT
        elif upper.startswith('EDIT:') and hasattr(self, 'last_outreach_id'):
            new_body = text[5:].strip()
            if not new_body:
                return "Please provide text after EDIT:"
            full_body = new_body + "\n\n" + settings.EMAIL_SIGNATURE
            outreach_id = self.last_outreach_id
            success = outreach_manager.send_professor_email(
                outreach_id, custom_body=full_body
            )
            if success:
                return "✅ Edited email sent to professor with attachments!"
            return "❌ Failed to send edited email"

        # PROF_EMAIL - Set professor email manually
        elif upper.startswith('PROF_EMAIL:') and hasattr(self, 'last_outreach_id'):
            email = text[11:].strip()
            outreach_id = self.last_outreach_id
            pending = outreach_manager.pending_professor_emails.get(str(outreach_id))
            if pending:
                pending['analysis'].email = email
                return f"✅ Professor email set to: {email}\nNow reply YES to send."
            return "No pending professor email found."

        # STATUS
        elif upper == 'STATUS':
            rows = outreach_manager.get_all_outreach()
            if not rows:
                return "No professor outreach records yet."
            status_msg = "📊 Professor Outreach History:\n\n"
            for row in rows[:10]:
                status_msg += (
                    f"- {row[1]} at {row[2]}\n"
                    f"  Type: {row[5]} | Score: {row[6]:.0%} | Status: {row[9]}\n\n"
                )
            return status_msg

        return None  # Not a professor command
