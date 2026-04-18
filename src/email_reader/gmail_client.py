import os
import base64
import pickle
from typing import List, Optional, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify'
]


class GmailClient:
    def __init__(self):
        self.service = None
        self.authenticate()

    def authenticate(self):
        """Authenticate with Gmail API using OAuth2."""
        creds = None

        if os.path.exists(settings.GMAIL_TOKEN_FILE):
            with open(settings.GMAIL_TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.GMAIL_CREDENTIALS_FILE,
                    SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(settings.GMAIL_TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)

        self.service = build('gmail', 'v1', credentials=creds)
        logger.info("Gmail API authenticated successfully ✅")

    def fetch_emails(
        self,
        max_results: int = 20,
        query: str = "is:unread"
    ) -> List[Dict[str, Any]]:
        """Fetch emails from Gmail."""
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            emails = []

            for message in messages:
                email_data = self._parse_email(message['id'])
                if email_data:
                    emails.append(email_data)

            logger.info(f"Fetched {len(emails)} emails")
            return emails

        except HttpError as error:
            logger.error(f"Error fetching emails: {error}")
            return []

    def _parse_email(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Parse a single email message."""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            headers = message['payload']['headers']

            email_data = {
                'id': message_id,
                'thread_id': message.get('threadId', ''),
                'label_ids': message.get('labelIds', []),
                'snippet': message.get('snippet', ''),
                'from': self._get_header(headers, 'From'),
                'to': self._get_header(headers, 'To'),
                'subject': self._get_header(headers, 'Subject'),
                'date': self._get_header(headers, 'Date'),
                'cc': self._get_header(headers, 'Cc'),
                'reply_to': self._get_header(headers, 'Reply-To'),
                'body_text': '',
                'body_html': '',
                'attachments': [],
                'is_read': 'UNREAD' not in message.get('labelIds', [])
            }

            self._extract_body(message['payload'], email_data)
            return email_data

        except HttpError as error:
            logger.error(f"Error parsing email {message_id}: {error}")
            return None

    def _extract_body(self, payload: dict, email_data: dict):
        """Recursively extract email body."""
        if 'body' in payload and payload['body'].get('data'):
            body = base64.urlsafe_b64decode(
                payload['body']['data']
            ).decode('utf-8', errors='ignore')

            mime_type = payload.get('mimeType', '')
            if 'text/plain' in mime_type:
                email_data['body_text'] += body
            elif 'text/html' in mime_type:
                email_data['body_html'] += body

        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('filename'):
                    email_data['attachments'].append({
                        'filename': part['filename'],
                        'mime_type': part.get('mimeType', ''),
                        'size': part.get('body', {}).get('size', 0)
                    })
                self._extract_body(part, email_data)

    def _get_header(self, headers: list, name: str) -> str:
        """Get a specific header value."""
        for header in headers:
            if header['name'].lower() == name.lower():
                return header['value']
        return ''

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        reply_to_message_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        cc: Optional[str] = None
    ) -> bool:
        """Send an email."""
        try:
            message = MIMEMultipart()
            message['to'] = to
            message['from'] = settings.USER_EMAIL
            message['subject'] = subject

            if cc:
                message['cc'] = cc

            if reply_to_message_id:
                message['In-Reply-To'] = reply_to_message_id
                message['References'] = reply_to_message_id

            message.attach(MIMEText(body, 'plain'))

            raw = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode('utf-8')

            body_payload = {'raw': raw}
            if thread_id:
                body_payload['threadId'] = thread_id

            sent = self.service.users().messages().send(
                userId='me',
                body=body_payload
            ).execute()

            logger.info(f"Email sent ✅ ID: {sent['id']}")
            return True

        except HttpError as error:
            logger.error(f"Error sending email: {error}")
            return False

    def mark_as_read(self, message_id: str):
        """Mark email as read."""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
        except HttpError as error:
            logger.error(f"Error marking as read: {error}")

    def add_label(self, message_id: str, label_name: str):
        """Add a label to an email."""
        try:
            label_id = self._get_or_create_label(label_name)
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': [label_id]}
            ).execute()
        except HttpError as error:
            logger.error(f"Error adding label: {error}")

    def _get_or_create_label(self, label_name: str) -> str:
        """Get existing label or create new one."""
        try:
            results = self.service.users().labels().list(
                userId='me'
            ).execute()

            for label in results.get('labels', []):
                if label['name'] == label_name:
                    return label['id']

            created = self.service.users().labels().create(
                userId='me',
                body={
                    'name': label_name,
                    'labelListVisibility': 'labelShow',
                    'messageListVisibility': 'show'
                }
            ).execute()
            return created['id']

        except HttpError as error:
            logger.error(f"Error with labels: {error}")
            return ''
