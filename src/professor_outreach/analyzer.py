import json
from typing import Dict, Any, List
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
  "matching_points": ["point 1", "point 2", "point 3"],
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

    def generate_email(
        self,
        professor_data: Dict[str, Any],
        analysis: ProfessorAnalysis,
        app_type: str
    ) -> ProfessorEmailDraft:
        """Generate email following EXACT template format."""

        prof_name = analysis.professor_name or professor_data.get("name", "Professor")
        prof_university = analysis.university or professor_data.get("university", "your institution")

        # Clean salutation
        salutation = prof_name
        for prefix in ["Prof. ", "Dr. ", "Professor ", "Doctor "]:
            salutation = salutation.replace(prefix, "")
        salutation = salutation.strip()

        # App type display
        app_display = "PhD" if app_type == "PHD" else "Masters"

        # Research areas
        research_areas = (
            analysis.professor_research_areas
            or analysis.matching_points
            or professor_data.get("research_interests", [])
        )
        research_text = " and ".join(research_areas[:3]) if research_areas else "your research areas"

        # Student matching research
        student_research = ", ".join(
            analysis.matching_points[:3]
        ) if analysis.matching_points else "deep learning and explainable AI"

        # Clean paper title
        specific_paper = analysis.specific_paper or ""
        specific_journal = analysis.specific_journal or ""

        # Remove journal name from paper title if accidentally included
        clean_paper = specific_paper
        if specific_journal and specific_journal in clean_paper:
            clean_paper = clean_paper.replace(f" - {specific_journal}", "").strip()
            clean_paper = clean_paper.replace(f"- {specific_journal}", "").strip()

        # Build paper mention line
        if clean_paper and specific_journal:
            paper_line = (
                f'In your research profile, I saw your latest research '
                f'article published in the {specific_journal}. '
                f'The title is "{clean_paper}".'
            )
        elif clean_paper:
            paper_line = (
                f'In your research profile, I saw your work titled '
                f'"{clean_paper}".'
            )
        else:
            paper_line = (
                f'In your research profile, I saw your work on '
                f'{research_text}.'
            )

        # Program text for paragraph 1
        if app_type == "PHD":
            para1_program = (
                f"apply for a PhD position under your supervision "
                f"at {prof_university} for the academic year 2026"
            )
        else:
            para1_program = (
                f"apply for the Master's program at {prof_university} "
                f"under your supervision for the Fall 2026 intake"
            )

        # Publications count
        pubs = self.student.get("publications", [])
        published_q1 = [p for p in pubs if "Published" in p.get("status","") and "MDPI" in p.get("journal","") or "Machine Learning" in p.get("journal","")]
        published = [p for p in pubs if p.get("status") == "Published"]
        revision = [p for p in pubs if "Revision" in p.get("status","") or "Processing" in p.get("status","")]
        proceedings = [p for p in pubs if p.get("type","") == "Conference Proceedings"]

        pub_lines = []
        if published:
            pub_lines.append(f"Q1 Journal: {len(published)} (published)")
        if revision:
            pub_lines.append(f"Journal under revision: {len(revision)}")
        if proceedings:
            pub_lines.append(f"Conference: {len(proceedings)} Published")
        pub_summary = "\n".join(pub_lines)

        # Education
        edu_lines = (
            f"B.Sc. in Computer Science and Engineering, "
            f"Daffodil International University, Bangladesh "
            f"(May 2022 – April 2026), CGPA: {self.student['cgpa']}\n\n"
            f"Erasmus+ Exchange Semester, Mälardalen University, "
            f"Sweden (Jan 2025 – Jun 2025)\n\n"
            f"Current Position: Teaching Assistant, "
            f"Department of CSE, DIU (October 2025 – Present)"
        )

        # Generate subject
        subject = self._generate_subject(research_areas, app_type)

        # Build email body - EXACT template format
        student_name = self.student["name"]
        student_cgpa = self.student["cgpa"]

        body = (
            f"Dear Professor {salutation},\n\n"
            f"Good day. I am {student_name}, an undergraduate B.Sc. student "
            f"& Teaching Assistant in Computer Science and Engineering at "
            f"Daffodil International University (DIU), Bangladesh, expecting "
            f"to graduate in April 2026. I wish to {para1_program}.\n\n"
            f"{paper_line} Also, you are working on {research_text}. "
            f"This inspires me to work under your supervision as a "
            f"{app_display} student. I have some research experience and "
            f"publications in {student_research}. "
            f"I am enthusiastic about conducting research under your supervision.\n\n"
            f"I am currently planning to apply for a {app_display} position "
            f"at {prof_university} for the academic year 2026.\n\n"
            f"Thank you for considering my application. I am genuinely excited "
            f"about the possibility of joining your research group. I look "
            f"forward to discussing my research plan further and am available "
            f"for a Zoom or Google Meet chat at your convenience.\n\n"
            f"Here is a brief profile overview:\n\n"
            f"{edu_lines}\n\n"
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
        app_type: str
    ) -> str:
        """Generate AI subject line."""

        prompt = ChatPromptTemplate.from_messages([
            ("system", "Generate ONE short professional email subject line. "
                      "Output ONLY the subject text, nothing else."),
            ("human", """
Student applying for: {app_type}
Professor research: {research}
Student background: Deep Learning, Computer Vision, Explainable AI

Write ONE subject line max 12 words.
Style examples:
- Prospective PhD Student - Deep Learning Research Inquiry
- Masters Application - Explainable AI and Medical Imaging
- PhD Inquiry - Machine Learning Research Collaboration

Output only the subject line:""")
        ])

        try:
            response = (prompt | self.llm).invoke({
                "app_type": app_type,
                "research": ", ".join(research_areas[:3])
            })
            subject = response.content.strip().replace('"', '').replace("'", '')
            if len(subject) > 100:
                subject = subject[:100]
            return subject
        except Exception as e:
            logger.error(f"Subject error: {e}")
            top = research_areas[0] if research_areas else "Your Research"
            return f"Prospective {app_type} Student - {top} Research Inquiry"
