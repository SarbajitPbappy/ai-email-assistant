from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator
from langchain_community.chat_models import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from config.settings import settings
from src.cv_parser.cv_extractor import CVExtractor
from src.utils.logger import get_logger
from src.utils.json_parser import extract_json_from_text

logger = get_logger(__name__)


class JobMatchResult(BaseModel):
    overall_match_score: float = Field(default=0.5)
    matching_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    recommendation: str = Field(default="MAYBE")
    reasoning: str = Field(default="")
    cover_letter_points: List[str] = Field(default_factory=list)
    job_title: str = Field(default="Unknown Position")
    company: str = Field(default="Unknown Company")

    @field_validator('company', 'job_title', mode='before')
    @classmethod
    def fix_string_fields(cls, v):
        if isinstance(v, list):
            return ", ".join(str(x) for x in v)
        return str(v) if v else "Unknown"

    @field_validator('recommendation', mode='before')
    @classmethod
    def fix_recommendation(cls, v):
        v = str(v).upper().strip()
        for opt in ["STRONG_APPLY", "APPLY", "MAYBE", "SKIP"]:
            if opt in v:
                return opt
        return "MAYBE"

    @field_validator('overall_match_score', mode='before')
    @classmethod
    def fix_score(cls, v):
        try:
            s = float(v)
            return s / 100 if s > 1.0 else min(max(s, 0.0), 1.0)
        except:
            return 0.5

    @field_validator('matching_skills', 'missing_skills', 'cover_letter_points', mode='before')
    @classmethod
    def fix_lists(cls, v):
        if isinstance(v, str):
            return [v] if v else []
        return v or []


class JobMatcher:
    def __init__(self):
        self.ollama = ChatOllama(
            model="llama3",
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.1
        )
        self.gemini = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=settings.GOOGLE_API_KEY
        )
        self.cv_extractor = CVExtractor()

    def _build_prompt(self):
        return ChatPromptTemplate.from_messages([
            ("system", """You are a job matching expert.
Output ONLY raw JSON, no markdown, no explanation.
Example:
{{"overall_match_score": 0.8, "matching_skills": ["Python", "ML"], "missing_skills": ["Java"], "recommendation": "APPLY", "reasoning": "Good match", "cover_letter_points": ["Highlight ML experience"], "job_title": "ML Engineer", "company": "TechCorp"}}

Recommendation must be one of: STRONG_APPLY, APPLY, MAYBE, SKIP
Score must be 0.0 to 1.0"""),
            ("human", """Match this candidate to the job:

CANDIDATE:
Name: {name}
Title: {title}
Skills: {skills}
Summary: {summary}
Target Roles: {desired_titles}

JOB DESCRIPTION:
{job_description}

Output JSON only:""")
        ])

    def match_job(self, job_description: str, job_metadata: Dict = None) -> JobMatchResult:
        """Match job against user profile."""
        profile = self.cv_extractor.get_profile()
        prompt = self._build_prompt()

        chain_input = {
            "name": profile.name,
            "title": profile.current_title,
            "skills": ", ".join(profile.technical_skills),
            "summary": profile.summary,
            "desired_titles": ", ".join(profile.desired_titles),
            "job_description": job_description[:2500]
        }

        # Try Ollama
        try:
            logger.info("Matching job with Ollama...")
            response = (prompt | self.ollama).invoke(chain_input)
            raw = response.content if hasattr(response, 'content') else str(response)
            data = extract_json_from_text(raw)
            if data:
                result = JobMatchResult(**data)
                logger.info(f"Match: {result.overall_match_score:.0%} | {result.recommendation}")
                if job_metadata:
                    result.job_title = job_metadata.get('title', result.job_title)
                    result.company = job_metadata.get('company', result.company)
                return result
            raise ValueError("No JSON from Ollama")
        except Exception as e:
            logger.warning(f"Ollama match failed: {e}. Trying Gemini...")

        # Try Gemini
        try:
            response = (prompt | self.gemini).invoke(chain_input)
            raw = response.content if hasattr(response, 'content') else str(response)
            data = extract_json_from_text(raw)
            if data:
                result = JobMatchResult(**data)
                logger.info(f"Gemini Match: {result.overall_match_score:.0%} | {result.recommendation}")
                return result
        except Exception as e:
            logger.error(f"Gemini match failed: {e}")

        return JobMatchResult(
            overall_match_score=0.5,
            recommendation="MAYBE",
            reasoning="Could not analyze"
        )

    def should_apply(self, match: JobMatchResult) -> bool:
        return (
            match.overall_match_score >= settings.MIN_MATCH_SCORE
            and match.recommendation in ["STRONG_APPLY", "APPLY"]
        )
