import os
from datetime import datetime
from typing import Dict, Any
import firebase_admin
from firebase_admin import firestore
from src.professor_outreach.scraper import ProfessorScraper
from src.professor_outreach.analyzer import ProfessorAnalyzer
from src.professor_outreach.email_sender import EmailWithAttachments
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

INTAKE_OPTIONS = [
    "Fall 2026",
    "Spring 2026",
    "Fall 2027",
    "Spring 2027",
    "Academic Year 2026",
    "Academic Year 2027"
]


class ProfessorTelegramHandler:
    """
    Full professor outreach workflow via Telegram.

    COMMANDS:
    PROF <anything>         - Start outreach
    PHD / MASTERS           - Select application type
    INTAKE <semester>       - Set intake semester
    YES                     - Send email
    NO                      - Discard
    EDIT: <new body>        - Edit body
    SUBJECT: <new subject>  - Change subject
    PROF_EMAIL: <email>     - Override email
    PROF_STATUS             - Show history
    PROF_HELP               - Show commands
    """

    def __init__(self, gmail_service):
        self.scraper = ProfessorScraper()
        self.analyzer = ProfessorAnalyzer()
        self.email_sender = EmailWithAttachments(gmail_service)
        self._init_db()

        self.pending: Dict[str, Any] = {}
        self.state = None
        self.current_outreach_id = None
        self.selected_intake = "Fall 2026"

    def _init_db(self):
        from src.professor_outreach.firebase_outreach import ProfessorOutreachDB
        self.outreach_db = ProfessorOutreachDB()
        logger.info("Professor DB ready ✅")

    def handle_message(self, text: str, send_func) -> bool:
        """Handle incoming Telegram message."""
        text = text.strip()
        upper = text.upper()

        # PROF - start new outreach
        if upper.startswith("PROF ") or upper == "PROF":
            content = text[5:].strip() if len(text) > 5 else ""
            if not content:
                send_func(
                    "Send professor info after PROF.\n\n"
                    "You can send:\n"
                    "- Name + university + email + research\n"
                    "- University profile URL\n"
                    "- Personal website URL\n"
                    "- Google Scholar URL + extra info"
                )
                return True
            self._handle_prof_command(content, send_func)
            return True

        # PHD or MASTERS
        elif upper in ["PHD", "MASTERS"] and self.state == "waiting_app_type":
            self._handle_app_type(upper, send_func)
            return True

        # INTAKE - set semester
        elif upper.startswith("INTAKE ") and self.state == "waiting_approval":
            intake = text[7:].strip()
            self._handle_intake(intake, send_func)
            return True

        # PUBS - manual publication summary
        elif upper.startswith("PUBS:") and self.state == "waiting_approval":
            pubs_text = text[5:].strip()
            self._handle_pubs(pubs_text, send_func)
            return True

        # MORE_INFO
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
        """Step 1: Extract professor data."""
        send_func("Analyzing professor info...")

        try:
            prof_data = self.scraper.extract(content)

            if prof_data.get("needs_more_info"):
                self.pending = {"professor_data": prof_data}
                self.state = "waiting_more_info"
                send_func(
                    "Google Scholar URL detected.\n\n"
                    "Please also send:\n"
                    "Name: Prof. X\n"
                    "University: University Name\n"
                    "Email: prof@university.edu\n"
                    "Research: area 1, area 2\n"
                    "Recent Paper: paper title - journal"
                )
                return

            self.pending = {"professor_data": prof_data}
            self.state = "waiting_app_type"
            self._show_detected_profile(prof_data, send_func)

        except Exception as e:
            logger.error(f"PROF error: {e}")
            send_func(f"Error: {e}")
            self.state = None

    def _handle_more_info(self, text: str, send_func):
        """Handle additional professor info."""
        send_func("Got it! Processing...")
        try:
            original = self.pending.get("professor_data", {})
            new_data = self.scraper.extract(text)
            merged = {
                "name": new_data.get("name") or original.get("name", ""),
                "university": new_data.get("university") or original.get("university", ""),
                "email": new_data.get("email") or original.get("email", ""),
                "research_interests": new_data.get("research_interests") or original.get("research_interests", []),
                "recent_papers": new_data.get("recent_papers") or original.get("recent_papers", []),
                "research_summary": new_data.get("research_summary") or original.get("research_summary", ""),
                "raw_content": original.get("raw_content", "") + "\n" + text,
                "needs_more_info": False
            }
            self.pending["professor_data"] = merged
            self.state = "waiting_app_type"
            self._show_detected_profile(merged, send_func)
        except Exception as e:
            send_func(f"Error: {e}")

    def _show_detected_profile(self, prof_data: dict, send_func):
        """Show detected profile and ask PHD/MASTERS."""
        name = prof_data.get("name") or "Not detected"
        university = prof_data.get("university") or "Not detected"
        email = prof_data.get("email") or "Not found"
        interests = prof_data.get("research_interests", [])

        interests_text = (
            "\n".join(f"- {i}" for i in interests[:5])
            if interests else "Not detected"
        )

        msg = (
            f"Professor detected:\n\n"
            f"Name: {name}\n"
            f"University: {university}\n"
            f"Email: {email}\n\n"
            f"Research:\n{interests_text}\n\n"
            f"Current intake: {self.selected_intake}\n"
            f"To change: INTAKE Fall 2026 / Spring 2027 etc.\n\n"
            f"Select application type:\n"
            f"PHD\n"
            f"MASTERS"
        )
        send_func(msg)

    def _handle_intake(self, intake: str, send_func):
        """Update intake semester."""
        self.selected_intake = intake

        # Regenerate email with new intake
        if self.pending.get("analysis") and self.pending.get("app_type"):
            send_func(f"Intake updated to: {intake}\nRegenerating email...")
            self._generate_and_show(
                self.pending["professor_data"],
                self.pending["analysis"],
                self.pending["app_type"],
                send_func
            )
        else:
            send_func(f"Intake set to: {intake}")

    def _handle_pubs(self, pubs_text: str, send_func):
        """Update publication summary manually from Telegram."""
        if not pubs_text:
            send_func(
                "Please provide publication summary after PUBS:\n\n"
                "Example:\n"
                "PUBS:\n"
                "Q1 Journal: 3 (published)\n"
                "Journal under revision: 1\n"
                "Conference: 2 Published"
            )
            return

        self.pending["manual_publications"] = pubs_text

        if self.pending.get("analysis") and self.pending.get("app_type"):
            send_func("Publication summary updated. Regenerating email...")
            self._generate_and_show(
                self.pending["professor_data"],
                self.pending["analysis"],
                self.pending["app_type"],
                send_func
            )
        else:
            send_func("Publication summary saved.")


    def _handle_app_type(self, app_type: str, send_func):
        """Generate email after PHD/MASTERS selected."""
        send_func(
            f"Generating {app_type} email for {self.selected_intake}...\n"
            f"Please wait ~1 minute."
        )

        try:
            prof_data = self.pending["professor_data"]
            analysis = self.analyzer.analyze(prof_data, app_type)
            self.pending["app_type"] = app_type
            self.pending["analysis"] = analysis
            self._generate_and_show(prof_data, analysis, app_type, send_func)

        except Exception as e:
            logger.error(f"App type error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            send_func(f"Error: {e}")
            self.state = None

    def _generate_and_show(self, prof_data, analysis, app_type, send_func):
        """Generate email and show full content in Telegram."""
        email_draft = self.analyzer.generate_email(
            prof_data,
            analysis,
            app_type,
            self.selected_intake,
            self.pending.get("manual_publications", "")
        )
        self.pending["email_draft"] = email_draft

        # Save to Firebase
        self.current_outreach_id = self.outreach_db.save_outreach({
            'professor_name': analysis.professor_name,
            'university': analysis.university,
            'professor_email': analysis.email or prof_data.get("email", ""),
            'application_type': app_type,
            'intake': self.selected_intake,
            'alignment_score': analysis.alignment_score,
            'recommendation': analysis.recommendation,
            'subject': email_draft.subject,
            'body': email_draft.body
        })

        self.state = "waiting_approval"

        score = analysis.alignment_score
        emoji = "🟢" if score >= 0.8 else "🟡" if score >= 0.6 else "🔴"
        matching = "\n".join(f"- {p}" for p in analysis.matching_points[:5])
        prof_email = analysis.email or prof_data.get("email", "Not found")

        # Send FULL email in parts to avoid Telegram limit
        # Part 1: Header info
        header = (
            f"PROFESSOR OUTREACH - {app_type}\n\n"
            f"Professor: {analysis.professor_name}\n"
            f"University: {analysis.university}\n"
            f"Email: {prof_email}\n"
            f"Intake: {self.selected_intake}\n\n"
            f"{emoji} Alignment: {score:.0%} | {analysis.recommendation}\n\n"
            f"Matching Research:\n{matching}"
        )
        send_func(header)

        # Part 2: Full email
        import time
        time.sleep(1)
        email_content = (
            f"SUBJECT:\n{email_draft.subject}\n\n"
            f"FULL EMAIL:\n"
            f"{'='*40}\n"
            f"{email_draft.body}\n"
            f"{'='*40}"
        )
        send_func(email_content)

        # Part 3: Commands
        time.sleep(1)
        commands = (
            f"Attachments: CV + Transcript\n\n"
            f"Commands:\n"
            f"YES - Send now\n"
            f"NO - Discard\n"
            f"EDIT: <new body> - Edit body\n"
            f"SUBJECT: <new subject> - Change subject\n"
            f"INTAKE <semester> - Change intake\n"
            f"PUBS: <publication summary> - Set publication counts\n"
            f"PROF_EMAIL: <email> - Change email"
        )
        send_func(commands)

    def _handle_yes(self, send_func):
        """Send email."""
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
                "Use PROF_EMAIL: email@university.edu to set email."
            )
        self.state = None

    def _handle_no(self, send_func):
        """Discard."""
        self._update_db("discarded")
        send_func("Professor email discarded.")
        self.state = None

    def _handle_edit(self, new_body: str, send_func):
        """Edit body and send."""
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
        """Change subject."""
        if not new_subject:
            send_func("Provide subject after SUBJECT:")
            return
        if not self.pending.get("email_draft"):
            send_func("No active email.")
            return
        self.pending["email_draft"].subject = new_subject
        if self.current_outreach_id:
            self.outreach_db.update_outreach(
                self.current_outreach_id,
                {'subject': new_subject}
            )
        send_func(f"Subject updated:\n{new_subject}\n\nReply YES to send.")

    def _handle_email_override(self, email: str, send_func):
        """Override professor email."""
        if not self.pending:
            send_func("No active outreach. Send PROF first.")
            return
        if self.pending.get("analysis"):
            self.pending["analysis"].email = email
        send_func(f"Professor email set:\n{email}\n\nReply YES to send.")

    def _handle_status(self, send_func):
        """Show history from Firebase."""
        rows = self.outreach_db.get_history(limit=10)
        if not rows:
            send_func("No outreach history yet.")
            return
        msg = "Professor Outreach History:\n\n"
        for row in rows:
            score = row.get("alignment_score", 0)
            score_str = f"{score:.0%}" if score else "N/A"
            msg += (
                f"- {row.get('professor_name')} at {row.get('university')}\n"
                f"  {row.get('application_type')} | {row.get('intake')} | "
                f"Score: {score_str} | {row.get('status')}\n\n"
            )
        send_func(msg)

    def _handle_help(self, send_func):
        """Show commands."""
        send_func(
            "PROFESSOR OUTREACH COMMANDS:\n\n"
            "PROF <info>           Start outreach\n"
            "PHD                   Apply for PhD\n"
            "MASTERS               Apply for Masters\n"
            "INTAKE <semester>     Set intake semester\n"
            "YES                   Send email\n"
            "NO                    Discard\n"
            "EDIT: <text>          Edit body\n"
            "SUBJECT: <text>       Change subject\n"
            "PROF_EMAIL: <email>   Set professor email\n"
            "PROF_STATUS           View history\n"
            "PROF_HELP             This help\n\n"
            "Intake examples:\n"
            "INTAKE Fall 2026\n"
            "INTAKE Spring 2027\n"
            "INTAKE Academic Year 2026"
        )

    def _send_email(self, body: str) -> bool:
        """Send email with attachments."""
        analysis = self.pending.get("analysis")
        email_draft = self.pending.get("email_draft")
        prof_data = self.pending.get("professor_data", {})

        if not analysis or not email_draft:
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

        return self.email_sender.send(
            to=prof_email,
            subject=email_draft.subject,
            body=body,
            attachments=attachments
        )

    def _update_db(self, status: str):
        """Update Firebase status."""
        if not self.current_outreach_id:
            return
        self.outreach_db.update_status(self.current_outreach_id, status)
