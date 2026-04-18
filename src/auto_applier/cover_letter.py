from typing import Any, Optional
from langchain_community.chat_models import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from config.settings import settings
from src.cv_parser.cv_extractor import CVExtractor
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CoverLetterGenerator:
    def __init__(self):
        self.ollama = ChatOllama(
            model="llama3",
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.7
        )
        self.gemini = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=settings.GOOGLE_API_KEY
        )
        self.cv_extractor = CVExtractor()

    def generate(
        self,
        job_description: str,
        match_result: Optional[Any] = None,
        max_words: int = 250
    ) -> str:
        """Generate a tailored cover letter."""
        profile = self.cv_extractor.get_profile()

        matching_skills = ""
        job_title = "this position"
        company = "your organization"

        if match_result:
            matching_skills = ", ".join(match_result.matching_skills[:6])
            job_title = match_result.job_title or job_title
            company = match_result.company or company

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert cover letter writer.
Write a compelling personalized cover letter.
Maximum {max_words} words.
Professional and enthusiastic tone.
End with the candidate name: {name}"""),
            ("human", """Write a cover letter for:
Job: {job_title} at {company}

Candidate:
Name: {name}
Title: {title}
Key Skills: {skills}
Matching Skills: {matching_skills}
Summary: {summary}

Job Description:
{job_description}""")
        ])

        chain_input = {
            "max_words": max_words,
            "name": profile.name,
            "job_title": job_title,
            "company": company,
            "title": profile.current_title,
            "skills": ", ".join(profile.technical_skills[:10]),
            "matching_skills": matching_skills,
            "summary": profile.summary,
            "job_description": job_description[:2000]
        }

        try:
            logger.info("Generating cover letter with Ollama...")
            result = (prompt | self.ollama).invoke(chain_input)
            logger.info("Cover letter generated successfully")
            return result.content
        except Exception as e:
            logger.warning(f"Ollama failed: {e}. Using Gemini...")
            try:
                result = (prompt | self.gemini).invoke(chain_input)
                return result.content
            except Exception as e2:
                logger.error(f"Cover letter generation failed: {e2}")
                return (
                    f"Dear Hiring Manager,\n\n"
                    f"I am writing to express my interest in {job_title} at {company}.\n\n"
                    f"Best regards,\n{profile.name}"
                )
