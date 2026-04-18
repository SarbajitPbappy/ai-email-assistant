import json
import textwrap
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
from src.utils.logger import get_logger
from src.utils.json_parser import extract_json_from_text

logger = get_logger(__name__)


def justify_text(text: str, width: int = 72) -> str:
    """Justify a single paragraph to a fixed column width."""
    words = text.split()
    lines, current_line, current_length = [], [], 0

    for word in words:
        if current_length + len(word) + len(current_line) <= width:
            current_line.append(word)
            current_length += len(word)
        else:
            lines.append(current_line)
            current_line = [word]
            current_length = len(word)
    if current_line:
        lines.append(current_line)

    justified_lines = []
    for i, line in enumerate(lines):
        if len(line) == 1 or i == len(lines) - 1:
            justified_lines.append(" ".join(line))
        else:
            total_spaces = width - sum(len(w) for w in line)
            gaps = len(line) - 1
            space, extra = divmod(total_spaces, gaps)
            justified_line = ""
            for j, word in enumerate(line[:-1]):
                justified_line += word + " " * (space + (1 if j < extra else 0))
            justified_line += line[-1]
            justified_lines.append(justified_line)

    return "\n".join(justified_lines)


def justify_block(text: str, width: int = 72) -> str:
    """Justify a full email body, preserving blank lines and list items."""
    result = []
    for line in text.split("\n"):
        stripped = line.strip()
        # Preserve blank lines, numbered lists, bullet points, and short lines
        if (
            not stripped
            or stripped[0].isdigit() and stripped[1:3] in (". ", ") ")
            or stripped.startswith(("-", "*", "•"))
            or len(stripped) < width // 2
        ):
            result.append(line)
        else:
            result.append(justify_text(stripped, width))
    return "\n".join(result)


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
        """Build numbered publication summary from student data."""
        pubs = self.student.get("publications", [])

        # Use pre-defined summary counts if available in student profile
        pub_summary = self.student.get("publication_summary", {})
        if pub_summary:
            q1 = pub_summary.get("q1_published", 0)
            revision = pub_summary.get("under_revision", 0)
            conference = pub_summary.get("conference_published", 0)
        else:
            # Derive counts from publications list
            q1 = sum(
                1 for p in pubs
                if "Q1" in p.get("journal", "") or "q1" in p.get("status", "").lower()
            )
            revision = sum(
                1 for p in pubs
                if "revision" in p.get("status", "").lower()
            )
            conference = sum(
                1 for p in pubs
                if "conference" in p.get("journal", "").lower()
                or "proceedings" in p.get("journal", "").lower()
                or "symposium" in p.get("journal", "").lower()
            )
            # Fallback: total published minus revision/conference = Q1
            if q1 == 0:
                published = sum(
                    1 for p in pubs
                    if "published" in p.get("status", "").lower()
                    and "conference" not in p.get("journal", "").lower()
                    and "proceedings" not in p.get("journal", "").lower()
                )
                q1 = published

        lines = [
            f"1. Q1 Journal: {q1} (Published)",
            f"2. Journal under revision: {revision}",
            f"3. Conference: {conference} (Published)",
        ]
        return "\n".join(lines)

    def generate_email(
        self,
        professor_data: Dict[str, Any],
        analysis: ProfessorAnalysis,
        app_type: str,
        intake: str = "Fall 2026",
        manual_publications: str = ""
    ) -> ProfessorEmailDraft:
        """Generate SHORT precise email (100-150 words max)."""

        prof_name = analysis.professor_name or professor_data.get("name", "Professor")
        prof_university = analysis.university or professor_data.get("university", "your institution")

        # Clean salutation
        salutation = prof_name
        for prefix in ["Prof. ", "Dr. ", "Professor ", "Doctor "]:
            salutation = salutation.replace(prefix, "")
        salutation = salutation.strip()

        # App type display
        app_display = "PhD" if app_type == "PHD" else "Master's"

        # Research areas - unique only
        research_areas = list(dict.fromkeys(
            analysis.professor_research_areas
            or analysis.matching_points
            or professor_data.get("research_interests", [])
        ))
        research_text = ", ".join(research_areas[:3]) if research_areas else "your research areas"

        # Student matching research - different from prof areas
        student_research = ", ".join(
            analysis.matching_points[:2]
        ) if analysis.matching_points else "deep learning and explainable AI"

        # Paper mention
        specific_paper = analysis.specific_paper or ""
        specific_journal = analysis.specific_journal or ""

        clean_paper = specific_paper
        if specific_journal and specific_journal in clean_paper:
            clean_paper = clean_paper.replace(f" - {specific_journal}", "").strip()

        if clean_paper and specific_journal:
            paper_line = (
                f"I came across your work \"{clean_paper}\" "
                f"published in {specific_journal}."
            )
        elif clean_paper:
            paper_line = f"I came across your work \"{clean_paper}\"."
        else:
            paper_line = f"Your research on {research_text} deeply interests me."

        # Program text
        if app_type == "PHD":
            program_text = (
                f"apply for a PhD position under your supervision "
                f"at {prof_university} for {intake}"
            )
        else:
            program_text = (
                f"apply for the {app_display} program at {prof_university} "
                f"under your supervision for {intake}"
            )

        # Numbered publication summary
        pubs_short = manual_publications.strip() if manual_publications.strip() \
            else self._build_publication_summary()

        # Generate subject
        subject = self._generate_subject(research_areas, app_type, prof_university)

        # Profile overview section
        profile_overview = (
            f"Here is a brief profile overview:\n\n"
            f"B.Sc. in Computer Science and Engineering, Daffodil International University, "
            f"Bangladesh (May 2022 – April 2026), CGPA: {self.student['cgpa']}\n"
            f"Erasmus+ Exchange Semester, Mälardalen University, Sweden (Jan 2025 – Jun 2025)\n"
            f"Current Position: Teaching Assistant, Department of CSE, DIU (October 2025 – Present)\n\n"
            f"Publications:\n{pubs_short}"
        )

        # Build STRICT 150-word email
        body = (
            f"Dear Professor {salutation},\n\n"
            f"Good day. I am {self.student['name']}, a final-year B.Sc. student "
            f"and Teaching Assistant at Daffodil International University (DIU), "
            f"Bangladesh (CGPA: {self.student['cgpa']}), expecting to graduate in "
            f"April 2026. I wish to {program_text}.\n\n"
            f"{paper_line} Your work on {research_text} aligns closely with my "
            f"research in {student_research}. I am enthusiastic about contributing "
            f"to your research group.\n\n"
            f"I completed an Erasmus+ Exchange at Mälardalen University, Sweden "
            f"(Jan–Jun 2025). I have attached my CV and transcript for your reference. "
            f"I would be honored to discuss further via Zoom or Google Meet at your convenience.\n\n"
            f"Thank you for your time and consideration.\n\n"
            f"{profile_overview}"
        )

        full_body = justify_block(body) + "\n\n" + self.student["signature"]

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
                      "Output ONLY the subject text."),
            ("human", """
Applying for: {app_type}
University: {university}
Professor research: {research}
Student: Deep Learning, Computer Vision, Explainable AI

Write ONE subject line max 10 words.
Examples:
- Prospective PhD Student - Explainable AI Research Inquiry
- Masters Inquiry - Computer Vision and Medical Imaging

Output only the subject:""")
        ])

        try:
            response = (prompt | self.llm).invoke({
                "app_type": "PhD" if app_type == "PHD" else "Masters",
                "university": university,
                "research": ", ".join(research_areas[:3])
            })
            subject = response.content.strip().replace('"', '').replace("'", '')
            return subject[:100]
        except:
            top = research_areas[0] if research_areas else "Research"
            return f"Prospective {'PhD' if app_type == 'PHD' else 'Masters'} Student - {top}"