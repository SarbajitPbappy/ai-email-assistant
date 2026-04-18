import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
from src.utils.logger import get_logger
from src.utils.json_parser import extract_json_from_text

logger = get_logger(__name__)


class ProfessorAnalysis(BaseModel):
    professor_name: str = ""
    university: str = ""
    email: str = ""
    alignment_score: float = 0.5
    matching_points: List[str] = Field(default_factory=list)
    specific_paper: str = ""
    specific_journal: str = ""
    professor_research_areas: List[str] = Field(default_factory=list)
    recommendation: str = "MAYBE"


class ProfessorEmailDraft(BaseModel):
    subject: str = ""
    body: str = ""


class ProfessorAnalyzer:

    def __init__(self):
        self.llm = ChatOllama(
            model="llama3",
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.2
        )
        with open(settings.RESEARCH_PROFILE_PATH, "r") as f:
            self.student = json.load(f)

    def analyze(
        self,
        professor_data: Dict[str, Any],
        app_type: str
    ) -> ProfessorAnalysis:
        """Analyze alignment between student and professor."""

        pubs = "\n".join([
            f"- {p['title']} ({p['journal']}, {p['status']})"
            for p in self.student.get("publications", [])
        ])
        interests = ", ".join(self.student.get("research_interests", []))

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert academic advisor. "
                       "Output ONLY raw JSON no markdown."),
            ("human", """
STUDENT:
Name: {student_name}
CGPA: {cgpa}
Research Interests: {interests}
Publications: {pubs}
Application: {app_type}

PROFESSOR:
Name: {prof_name}
University: {prof_university}
Research Info: {prof_summary}

Return ONLY this JSON:
{{
  "professor_name": "full professor name",
  "university": "university name",
  "email": "email or empty string",
  "alignment_score": 0.85,
  "matching_points": ["specific point 1", "specific point 2", "specific point 3"],
  "specific_paper": "exact paper title if mentioned else empty",
  "specific_journal": "exact journal name if mentioned else empty",
  "professor_research_areas": ["area 1", "area 2", "area 3"],
  "recommendation": "STRONG_APPLY"
}}
""")
        ])

        try:
            response = (prompt | self.llm).invoke({
                "student_name": self.student["name"],
                "cgpa": self.student["cgpa"],
                "interests": interests,
                "pubs": pubs,
                "app_type": app_type,
                "prof_name": professor_data.get("name", "Unknown"),
                "prof_university": professor_data.get("university", "Unknown"),
                "prof_summary": professor_data.get(
                    "raw_content",
                    professor_data.get("research_summary", "")
                )[:1500]
            })

            data = extract_json_from_text(response.content)
            if data:
                if not data.get("email") and professor_data.get("email"):
                    data["email"] = professor_data["email"]
                analysis = ProfessorAnalysis(**data)
                logger.info(
                    f"Analysis: {analysis.professor_name} | "
                    f"{analysis.alignment_score:.0%} | "
                    f"{analysis.recommendation}"
                )
                return analysis

        except Exception as e:
            logger.error(f"Analysis error: {e}")

        return ProfessorAnalysis(
            professor_name=professor_data.get("name", "Unknown"),
            university=professor_data.get("university", "Unknown"),
            email=professor_data.get("email", ""),
            alignment_score=0.5,
            recommendation="MAYBE"
        )

    def _build_publication_summary(self) -> str:
        """Build publication summary from student profile."""
        pubs = self.student.get("publications", [])

        published = sum(
            1 for p in pubs
            if "Published" in p.get("status", "")
            and "Conference" not in p.get("type", "")
            and "Proceedings" not in p.get("journal", "")
        )
        revision = sum(
            1 for p in pubs
            if "Revision" in p.get("status", "")
            or "Processing" in p.get("status", "")
        )
        conference = sum(
            1 for p in pubs
            if p.get("type", "") == "Conference Proceedings"
            or "Proceedings" in p.get("journal", "")
            or "Symposium" in p.get("journal", "")
        )

        lines = []
        if published:
            lines.append(f"Q1 Journal: {published} (published)")
        if revision:
            lines.append(f"Journal under revision: {revision}")
        if conference:
            lines.append(f"Conference: {conference} Published")

        return "\n".join(lines) if lines else "Q1 Journal: 1 (published)"

    def generate_email(
        self,
        professor_data: Dict[str, Any],
        analysis: ProfessorAnalysis,
        app_type: str,
        intake: str = "Fall 2026",
        manual_publications: str = ""
    ) -> ProfessorEmailDraft:
        """Generate email following exact preferred format."""

        prof_name = analysis.professor_name or professor_data.get("name", "Professor")
        prof_university = (
            analysis.university
            or professor_data.get("university", "your institution")
        )

        # Clean salutation - remove titles
        salutation = prof_name
        for prefix in ["Prof. ", "Dr. ", "Professor ", "Doctor "]:
            salutation = salutation.replace(prefix, "")
        salutation = salutation.strip()

        # App type display
        app_display = "PhD" if app_type == "PHD" else "Master's"

        # Research areas - remove duplicates
        research_areas = list(dict.fromkeys(
            analysis.professor_research_areas
            or analysis.matching_points
            or professor_data.get("research_interests", [])
        ))
        research_text = (
            ", ".join(research_areas[:3])
            if research_areas
            else "your research areas"
        )

        # Paper and journal mention
        specific_paper = analysis.specific_paper or ""
        specific_journal = analysis.specific_journal or ""

        clean_paper = specific_paper
        if specific_journal and specific_journal in clean_paper:
            clean_paper = clean_paper.replace(
                f" - {specific_journal}", ""
            ).strip()

        if clean_paper and specific_journal:
            paper_line = (
                f'In your research profile, I saw your latest research article '
                f'published in the {specific_journal}. '
                f'The title is "{clean_paper}".'
            )
        elif clean_paper:
            paper_line = (
                f'In your research profile, I saw your work titled "{clean_paper}".'
            )
        else:
            paper_line = (
                f'In your research profile, I saw your work on {research_text}.'
            )

        # Program text
        if app_type == "PHD":
            program_text = (
                f"apply for a PhD position under your supervision "
                f"at {prof_university} for {intake}"
            )
        else:
            program_text = (
                f"apply for the {app_display} program at {prof_university} "
                f"under your supervision for the {intake} intake"
            )

        # Publication summary
        pub_summary = (
            manual_publications.strip()
            if manual_publications.strip()
            else self._build_publication_summary()
        )

        # Subject line
        subject = self._generate_subject(research_areas, app_type, prof_university)

        # Build email body - exact preferred format
        student_name = self.student["name"]
        student_cgpa = self.student["cgpa"]

        body = (
            f"Dear Professor {salutation},\n\n"
            f"Good day. I am {student_name}, an undergraduate B.Sc. student "
            f"& Teaching Assistant in Computer Science and Engineering at "
            f"Daffodil International University (DIU), Bangladesh, expecting "
            f"to graduate in April 2026. I wish to {program_text}.\n\n"
            f"{paper_line} Also, you are working on {research_text}. "
            f"This inspires me to work under your supervision as a "
            f"{app_display} student. I have some research experience and "
            f"publications in deep learning, computer vision, and explainable "
            f"AI. I am enthusiastic about conducting research under your "
            f"supervision.\n\n"
            f"Thank you for considering my application. I am genuinely excited "
            f"about the possibility of joining your research group. I look "
            f"forward to discussing my research plan further and am available "
            f"for a Zoom or Google Meet chat at your convenience.\n\n"
            f"Here is a brief profile overview:\n\n"
            f"B.Sc. in Computer Science and Engineering, Daffodil International "
            f"University, Bangladesh (May 2022 – April 2026), "
            f"CGPA: {student_cgpa}\n\n"
            f"Erasmus+ Exchange Semester, Mälardalen University, Sweden "
            f"(Jan 2025 – Jun 2025)\n\n"
            f"Current Position: Teaching Assistant, Department of CSE, DIU "
            f"(October 2025 – Present)\n\n"
            f"Publications:\n"
            f"{pub_summary}\n\n"
            f"I have attached my CV and transcript for your reference."
        )

        full_body = body + "\n\n" + self.student["signature"]

        logger.info(f"Email generated: {subject}")
        return ProfessorEmailDraft(subject=subject, body=full_body)

    def _generate_subject(
        self,
        research_areas: List[str],
        app_type: str,
        university: str
    ) -> str:
        """Generate AI subject line."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Generate ONE short professional email subject line. "
                       "Output ONLY the subject text, nothing else."),
            ("human", """
Applying for: {app_type}
University: {university}
Professor research: {research}
Student background: Deep Learning, Computer Vision, Explainable AI

Write ONE subject line max 10 words.
Examples:
- Prospective PhD Student - Explainable AI Research Inquiry
- Masters Inquiry - Computer Vision and Medical Imaging

Output only the subject line:""")
        ])

        try:
            response = (prompt | self.llm).invoke({
                "app_type": "PhD" if app_type == "PHD" else "Masters",
                "university": university,
                "research": ", ".join(research_areas[:3])
            })
            subject = response.content.strip().replace('"', '').replace("'", '')
            if len(subject) > 100:
                subject = subject[:100]
            return subject
        except Exception as e:
            logger.error(f"Subject generation error: {e}")
            top = research_areas[0] if research_areas else "Research"
            return (
                f"Prospective {'PhD' if app_type == 'PHD' else 'Masters'} "
                f"Student - {top}"
            )
