import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional
from src.professor_outreach.scraper import ProfessorScraper
from src.professor_outreach.analyzer import ProfessorAnalyzer
from src.professor_outreach.email_sender import EmailWithAttachments
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


class ProfessorOutreachManager:
    """Main manager for professor outreach workflow."""

    def __init__(self, gmail_service):
        self.scraper = ProfessorScraper()
        self.analyzer = ProfessorAnalyzer()
        self.email_sender = EmailWithAttachments(gmail_service)
        self.pending_professor_emails: Dict[str, Dict] = {}
        self._init_db()

    def _init_db(self):
        """Initialize professor outreach tracking database."""
        conn = sqlite3.connect('data/assistant.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS professor_outreach (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                professor_name TEXT,
                university TEXT,
                email TEXT,
                url TEXT,
                application_type TEXT,
                alignment_score REAL,
                recommendation TEXT,
                email_subject TEXT,
                email_body TEXT,
                status TEXT DEFAULT 'pending',
                sent_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Professor outreach DB initialized ✅")

    def process_professor_request(
        self,
        input_text: str,
        application_type: str = "PhD"
    ) -> Dict[str, Any]:
        """
        Process a professor request from Telegram.
        input_text can be URL or text summary.
        """
        logger.info(f"Processing professor request: {input_text[:100]}")

        # Step 1: Scrape or parse professor info
        if input_text.startswith('http'):
            professor_data = self.scraper.scrape(input_text)
        else:
            professor_data = self.scraper.parse_text_summary(input_text)

        logger.info(f"Professor data collected: {professor_data.get('name', 'Unknown')}")

        # Step 2: Analyze alignment
        analysis = self.analyzer.analyze_professor(
            professor_data,
            application_type
        )

        logger.info(
            f"Analysis: {analysis.alignment_score:.0%} match | "
            f"{analysis.recommendation}"
        )

        # Step 3: Generate email
        email_draft = self.analyzer.generate_email(
            professor_data,
            analysis,
            application_type
        )

        # Step 4: Save to database
        conn = sqlite3.connect('data/assistant.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO professor_outreach
            (professor_name, university, email, url, application_type,
             alignment_score, recommendation, email_subject, email_body, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        ''', (
            analysis.professor_name,
            analysis.university,
            analysis.email or professor_data.get('email', ''),
            professor_data.get('url', ''),
            application_type,
            analysis.alignment_score,
            analysis.recommendation,
            email_draft.subject,
            email_draft.body
        ))
        outreach_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Step 5: Store for pending approval
        self.pending_professor_emails[str(outreach_id)] = {
            'outreach_id': outreach_id,
            'professor_data': professor_data,
            'analysis': analysis,
            'email_draft': email_draft,
            'application_type': application_type
        }

        return {
            'outreach_id': outreach_id,
            'professor_data': professor_data,
            'analysis': analysis,
            'email_draft': email_draft
        }

    def send_professor_email(
        self,
        outreach_id: int,
        custom_body: Optional[str] = None
    ) -> bool:
        """Send email with CV and transcript attached."""
        pending = self.pending_professor_emails.get(str(outreach_id))
        if not pending:
            # Try to load from database
            conn = sqlite3.connect('data/assistant.db')
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM professor_outreach WHERE id = ?',
                (outreach_id,)
            )
            row = cursor.fetchone()
            conn.close()
            if not row:
                return False

        analysis = pending['analysis']
        email_draft = pending['email_draft']

        # Get professor email
        prof_email = analysis.email
        if not prof_email:
            prof_email = pending['professor_data'].get('email', '')

        if not prof_email:
            logger.error("No professor email found!")
            return False

        # Use custom body if provided
        body = custom_body if custom_body else email_draft.body

        # Prepare attachments
        attachments = []
        if os.path.exists(settings.CV_PATH):
            attachments.append(settings.CV_PATH)
        if os.path.exists('data/transcript.pdf'):
            attachments.append('data/transcript.pdf')

        # Send email
        success = self.email_sender.send(
            to=prof_email,
            subject=email_draft.subject,
            body=body,
            attachments=attachments
        )

        if success:
            # Update database
            conn = sqlite3.connect('data/assistant.db')
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE professor_outreach SET status = ?, sent_at = ? WHERE id = ?',
                ('sent', datetime.utcnow(), outreach_id)
            )
            conn.commit()
            conn.close()
            logger.info(f"Professor email sent to {prof_email} ✅")

        return success

    def get_all_outreach(self) -> list:
        """Get all professor outreach records."""
        conn = sqlite3.connect('data/assistant.db')
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM professor_outreach ORDER BY created_at DESC'
        )
        rows = cursor.fetchall()
        conn.close()
        return rows

    def build_telegram_message(self, result: Dict[str, Any]) -> str:
        """Build Telegram notification for professor outreach."""
        analysis = result['analysis']
        email_draft = result['email_draft']
        outreach_id = result['outreach_id']

        app_type = result.get('application_type', 'PhD')
        score_emoji = (
            "🟢" if analysis.alignment_score >= 0.8
            else "🟡" if analysis.alignment_score >= 0.6
            else "🔴"
        )

        # Clean text for Telegram
        body_preview = email_draft.body[:800]

        message = f"""🎓 PROFESSOR OUTREACH - {app_type}

Professor: {analysis.professor_name}
University: {analysis.university}
Email: {analysis.email or 'Not found - add manually'}

{score_emoji} Alignment Score: {analysis.alignment_score:.0%}
Recommendation: {analysis.recommendation}

Matching Interests:
{chr(10).join(f'- {i}' for i in analysis.matching_interests[:5])}

Why Good Fit:
{analysis.why_good_fit[:300]}

GENERATED EMAIL:
Subject: {email_draft.subject}
------------------
{body_preview}
------------------

Attachments: CV + Transcript will be attached automatically

Reply with:
YES - Send email with CV + Transcript attached
NO - Discard
EDIT: <your new body text> - Edit body and send
PROF_EMAIL: <email@university.edu> - Set professor email first

Outreach ID: {outreach_id}"""

        return message
