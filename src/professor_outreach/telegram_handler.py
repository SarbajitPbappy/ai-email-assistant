import os
import sqlite3
from datetime import datetime
from typing import Dict, Any
from src.professor_outreach.scraper import ProfessorScraper
from src.professor_outreach.analyzer import ProfessorAnalyzer
from src.professor_outreach.email_sender import EmailWithAttachments
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


class ProfessorTelegramHandler:
    """
    Full professor outreach workflow via Telegram.

    COMMANDS:
    PROF <anything>        - Start outreach (URL/text/mixed)
    PHD / MASTERS          - Select application type
    YES                    - Send email
    NO                     - Discard
    EDIT: <new body>       - Edit body and send
    SUBJECT: <new subject> - Change subject line
    PROF_EMAIL: <email>    - Override professor email
    PROF_STATUS            - Show history
    PROF_HELP              - Show all commands
    """

    def __init__(self, gmail_service):
        self.scraper = ProfessorScraper()
        self.analyzer = ProfessorAnalyzer()
        self.email_sender = EmailWithAttachments(gmail_service)
        self._init_db()

        self.pending: Dict[str, Any] = {}
        self.state = None
        self.current_outreach_id = None

    def _init_db(self):
        conn = sqlite3.connect("data/assistant.db")
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS professor_outreach (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                professor_name TEXT,
                university TEXT,
                professor_email TEXT,
                application_type TEXT,
                alignment_score REAL,
                recommendation TEXT,
                subject TEXT,
                body TEXT,
                status TEXT DEFAULT "pending",
                sent_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Professor DB ready ✅")

    def handle_message(self, text: str, send_func) -> bool:
        """Handle incoming Telegram message. Returns True if handled."""
        text = text.strip()
        upper = text.upper()

        # PROF - start new outreach
        if upper.startswith("PROF ") or upper == "PROF":
            content = text[5:].strip() if len(text) > 5 else ""
            if not content:
                send_func(
                    "Send professor info after PROF.\n\n"
                    "You can send:\n"
                    "- Professor name + university + email + research\n"
                    "- University profile URL\n"
                    "- Google Scholar URL + extra info\n"
                    "- Any mix of the above\n\n"
                    "NOTE: Google Scholar alone won't work.\n"
                    "Add name/email/research alongside the URL."
                )
                return True
            self._handle_prof_command(content, send_func)
            return True

        # PHD or MASTERS
        elif upper in ["PHD", "MASTERS"] and self.state == "waiting_app_type":
            self._handle_app_type(upper, send_func)
            return True

        # MORE_INFO - user pasting additional professor info
        elif self.state == "waiting_more_info":
            self._handle_more_info(text, send_func)
            return True

        # YES
        elif upper == "YES" and self.state == "waiting_approval":
            self._handle_yes(send_func)
            return True

        # NO
        elif upper == "NO" and self.state == "waiting_approval":
            self._handle_no(send_func)
            return True

        # EDIT:
        elif upper.startswith("EDIT:") and self.state == "waiting_approval":
            self._handle_edit(text[5:].strip(), send_func)
            return True

        # SUBJECT:
        elif upper.startswith("SUBJECT:") and self.state == "waiting_approval":
            self._handle_subject(text[8:].strip(), send_func)
            return True

        # PROF_EMAIL:
        elif upper.startswith("PROF_EMAIL:"):
            self._handle_email_override(text[11:].strip(), send_func)
            return True

        # PROF_STATUS
        elif upper == "PROF_STATUS":
            self._handle_status(send_func)
            return True

        # PROF_HELP
        elif upper == "PROF_HELP":
            self._handle_help(send_func)
            return True

        return False

    def _handle_prof_command(self, content: str, send_func):
        """Extract professor data from any input."""
        send_func("Analyzing professor info...")

        try:
            prof_data = self.scraper.extract(content)

            # Check if we need more info (Scholar URL only)
            if prof_data.get("needs_more_info"):
                self.pending = {"professor_data": prof_data}
                self.state = "waiting_more_info"
                send_func(
                    "Google Scholar URL detected.\n\n"
                    "Google Scholar blocks automated access.\n\n"
                    "Please paste the professor's info:\n\n"
                    "Name: Prof. X\n"
                    "University: University Name\n"
                    "Email: prof@university.edu\n"
                    "Research: area 1, area 2\n"
                    "Recent Paper: paper title - journal\n\n"
                    "You can copy this from their Scholar page."
                )
                return

            self.pending = {"professor_data": prof_data}
            self.state = "waiting_app_type"
            self._show_detected_profile(prof_data, send_func)

        except Exception as e:
            logger.error(f"PROF error: {e}")
            send_func(f"Error analyzing professor: {e}")
            self.state = None

    def _handle_more_info(self, text: str, send_func):
        """Handle additional info after Scholar URL."""
        send_func("Got it! Processing...")

        try:
            # Combine with original data
            original = self.pending.get("professor_data", {})
            new_data = self.scraper.extract(text)

            # Merge: prefer new data but keep original where new is empty
            merged = {
                "name": new_data.get("name") or original.get("name", ""),
                "university": new_data.get("university") or original.get("university", ""),
                "department": new_data.get("department") or original.get("department", ""),
                "email": new_data.get("email") or original.get("email", ""),
                "research_interests": (
                    new_data.get("research_interests")
                    or original.get("research_interests", [])
                ),
                "recent_papers": (
                    new_data.get("recent_papers")
                    or original.get("recent_papers", [])
                ),
                "research_summary": (
                    new_data.get("research_summary")
                    or original.get("research_summary", "")
                ),
                "raw_content": (
                    original.get("raw_content", "")
                    + "\n" + text
                ),
                "needs_more_info": False
            }

            self.pending["professor_data"] = merged
            self.state = "waiting_app_type"
            self._show_detected_profile(merged, send_func)

        except Exception as e:
            logger.error(f"More info error: {e}")
            send_func(f"Error: {e}")

    def _show_detected_profile(self, prof_data: dict, send_func):
        """Show detected profile and ask for PHD/MASTERS."""
        name = prof_data.get("name") or "Not detected"
        university = prof_data.get("university") or "Not detected"
        email = prof_data.get("email") or "Not found"
        interests = prof_data.get("research_interests", [])
        papers = prof_data.get("recent_papers", [])

        interests_text = (
            "\n".join(f"- {i}" for i in interests[:5])
            if interests else "Not detected"
        )
        papers_text = (
            "\n".join(f"- {p.get('title', '')[:60]}" for p in papers[:3])
            if papers else "Not detected"
        )

        msg = (
            f"Professor detected:\n\n"
            f"Name: {name}\n"
            f"University: {university}\n"
            f"Email: {email}\n\n"
            f"Research Interests:\n{interests_text}\n\n"
            f"Recent Papers:\n{papers_text}\n\n"
            f"Now reply with:\n"
            f"PHD\n"
            f"MASTERS\n\n"
            f"Or fix email first:\n"
            f"PROF_EMAIL: correct@email.edu"
        )
        send_func(msg)

    def _handle_app_type(self, app_type: str, send_func):
        """Generate email after PHD/MASTERS selected."""
        send_func(
            f"Generating {app_type} email...\n"
            f"Analyzing research alignment.\n"
            f"Please wait ~1 minute."
        )

        try:
            prof_data = self.pending["professor_data"]
            analysis = self.analyzer.analyze(prof_data, app_type)
            email_draft = self.analyzer.generate_email(
                prof_data, analysis, app_type
            )

            self.pending.update({
                "app_type": app_type,
                "analysis": analysis,
                "email_draft": email_draft
            })

            # Save to DB
            conn = sqlite3.connect("data/assistant.db")
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO professor_outreach
                (professor_name, university, professor_email,
                 application_type, alignment_score, recommendation,
                 subject, body, status)
                VALUES (?,?,?,?,?,?,?,?,"pending")
            ''', (
                analysis.professor_name,
                analysis.university,
                analysis.email or prof_data.get("email", ""),
                app_type,
                analysis.alignment_score,
                analysis.recommendation,
                email_draft.subject,
                email_draft.body
            ))
            self.current_outreach_id = cursor.lastrowid
            conn.commit()
            conn.close()

            self.state = "waiting_approval"

            score = analysis.alignment_score
            emoji = "🟢" if score >= 0.8 else "🟡" if score >= 0.6 else "🔴"
            matching = "\n".join(
                f"- {p}" for p in analysis.matching_points[:5]
            )
            prof_email = analysis.email or prof_data.get("email", "Not found")

            msg = (
                f"PROFESSOR OUTREACH - {app_type}\n\n"
                f"Professor: {analysis.professor_name}\n"
                f"University: {analysis.university}\n"
                f"Email: {prof_email}\n\n"
                f"{emoji} Alignment: {score:.0%} | {analysis.recommendation}\n\n"
                f"Matching Research:\n{matching}\n\n"
                f"SUBJECT:\n{email_draft.subject}\n\n"
                f"EMAIL BODY:\n"
                f"------------------\n"
                f"{email_draft.body[:1200]}\n"
                f"------------------\n\n"
                f"Attachments: CV + Transcript\n\n"
                f"Commands:\n"
                f"YES - Send now\n"
                f"NO - Discard\n"
                f"EDIT: <new body>\n"
                f"SUBJECT: <new subject>\n"
                f"PROF_EMAIL: <email>"
            )
            send_func(msg)

        except Exception as e:
            logger.error(f"App type error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            send_func(f"Error generating email: {e}")
            self.state = None

    def _handle_yes(self, send_func):
        success = self._send_email(self.pending["email_draft"].body)
        if success:
            send_func(
                "Email sent to professor!\n"
                "CV and Transcript attached.\n"
                "Good luck!"
            )
            self._update_db("sent")
        else:
            send_func(
                "Failed to send.\n"
                "Professor email missing?\n"
                "Use: PROF_EMAIL: email@university.edu"
            )
        self.state = None

    def _handle_no(self, send_func):
        self._update_db("discarded")
        send_func("Professor email discarded.")
        self.state = None

    def _handle_edit(self, new_body: str, send_func):
        if not new_body:
            send_func("Provide text after EDIT:")
            return
        full_body = new_body + "\n\n" + settings.EMAIL_SIGNATURE
        success = self._send_email(full_body)
        if success:
            send_func("Edited email sent with attachments!")
            self._update_db("sent")
        else:
            send_func("Failed to send.")
        self.state = None

    def _handle_subject(self, new_subject: str, send_func):
        if not new_subject:
            send_func("Provide subject after SUBJECT:")
            return
        if not self.pending.get("email_draft"):
            send_func("No active email. Send PROF first.")
            return
        self.pending["email_draft"].subject = new_subject
        if self.current_outreach_id:
            conn = sqlite3.connect("data/assistant.db")
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE professor_outreach SET subject=? WHERE id=?",
                (new_subject, self.current_outreach_id)
            )
            conn.commit()
            conn.close()
        send_func(
            f"Subject updated:\n{new_subject}\n\n"
            f"Reply YES to send."
        )

    def _handle_email_override(self, email: str, send_func):
        if not self.pending:
            send_func("No active outreach. Send PROF first.")
            return
        if self.pending.get("analysis"):
            self.pending["analysis"].email = email
        send_func(f"Professor email set to:\n{email}\n\nReply YES to send.")

    def _handle_status(self, send_func):
        conn = sqlite3.connect("data/assistant.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT professor_name, university, application_type, "
            "alignment_score, status, created_at "
            "FROM professor_outreach ORDER BY created_at DESC LIMIT 10"
        )
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            send_func("No outreach history yet.")
            return
        msg = "Professor Outreach History:\n\n"
        for row in rows:
            score = f"{row[3]:.0%}" if row[3] else "N/A"
            msg += (
                f"- {row[0]}\n"
                f"  {row[2]} at {row[1]}\n"
                f"  Score: {score} | {row[4]}\n\n"
            )
        send_func(msg)

    def _handle_help(self, send_func):
        send_func(
            "PROFESSOR OUTREACH COMMANDS:\n\n"
            "PROF <info>          Start outreach\n"
            "PHD                  Apply for PhD\n"
            "MASTERS              Apply for Masters\n"
            "YES                  Send email\n"
            "NO                   Discard\n"
            "EDIT: <text>         Edit body\n"
            "SUBJECT: <text>      Change subject\n"
            "PROF_EMAIL: <email>  Set professor email\n"
            "PROF_STATUS          View history\n"
            "PROF_HELP            This help\n\n"
            "TIP: For Google Scholar URL,\n"
            "add name+email+research alongside it."
        )

    def _send_email(self, body: str) -> bool:
        analysis = self.pending.get("analysis")
        email_draft = self.pending.get("email_draft")
        prof_data = self.pending.get("professor_data", {})

        if not analysis or not email_draft:
            logger.error("No pending email data")
            return False

        prof_email = analysis.email or prof_data.get("email", "")
        if not prof_email:
            logger.error("Professor email not found")
            return False

        attachments = []
        if os.path.exists(settings.CV_PATH):
            attachments.append(settings.CV_PATH)
        if os.path.exists("data/transcript.pdf"):
            attachments.append("data/transcript.pdf")

        logger.info(f"Sending to {prof_email} | {len(attachments)} attachments")

        return self.email_sender.send(
            to=prof_email,
            subject=email_draft.subject,
            body=body,
            attachments=attachments
        )

    def _update_db(self, status: str):
        if not self.current_outreach_id:
            return
        conn = sqlite3.connect("data/assistant.db")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE professor_outreach SET status=?, sent_at=? WHERE id=?",
            (status, datetime.utcnow().isoformat(), self.current_outreach_id)
        )
        conn.commit()
        conn.close()
