import os
import os
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


class EmailWithAttachments:
    """Sends emails with PDF attachments (CV, Transcript)."""

    def __init__(self, gmail_service):
        self.service = gmail_service

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: List[str] = None
    ) -> bool:
        """
        Send email with optional attachments.
        attachments: list of file paths
        """
        try:
            message = MIMEMultipart()
            message['to'] = to
            message['from'] = settings.USER_EMAIL
            message['subject'] = subject

            # Add body
            message.attach(MIMEText(body, 'plain'))

            # Add attachments
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        self._attach_file(message, file_path)
                        logger.info(f"Attached: {file_path}")
                    else:
                        logger.warning(f"File not found: {file_path}")

            # Encode and send
            raw = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode('utf-8')

            sent = self.service.users().messages().send(
                userId='me',
                body={'raw': raw}
            ).execute()

            logger.info(f"Email sent with attachments! ID: {sent['id']}")
            return True

        except Exception as e:
            logger.error(f"Error sending email with attachments: {e}")
            return False

    def _attach_file(self, message: MIMEMultipart, file_path: str):
        """Attach a file to the email."""
        filename = os.path.basename(file_path)

        with open(file_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())

        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename="{filename}"'
        )
        message.attach(part)
