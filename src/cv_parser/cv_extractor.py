import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import PyPDF2
from langchain_community.chat_models import ChatOllama
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field, field_validator
from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

class UserProfile(BaseModel):
    name: str = Field(description="Full name")
    email: str = Field(description="Primary email address as a single string")
    current_title: str = Field(description="Current job title or student status")
    years_of_experience: int = Field(description="Total years of experience or study")
    technical_skills: List[str] = Field(description="List of technical skills")
    programming_languages: List[str] = Field(default_factory=list)
    summary: str = Field(description="2-3 sentence professional summary")
    desired_titles: List[str] = Field(description="Roles the user is qualified for")

    @field_validator('email', mode='before')
    @classmethod
    def fix_email(cls, v):
        """If LLM returns list of emails, take the first one."""
        if isinstance(v, list):
            return v[0] if v else ""
        return str(v)

    @field_validator('desired_titles', mode='before')
    @classmethod
    def fix_titles(cls, v):
        """Handle if titles come as a string."""
        if isinstance(v, str):
            return [t.strip() for t in v.split(',')]
        return v

    @field_validator('technical_skills', mode='before')
    @classmethod
    def fix_skills(cls, v):
        """Handle if skills come as a string."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(',')]
        return v


class CVExtractor:
    def __init__(self):
        self.llm = ChatOllama(
            model="llama3",
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.1
        )
        self.parser = PydanticOutputParser(pydantic_object=UserProfile)
        self.profile: Optional[UserProfile] = None
        self._load_cached_profile()

    def _load_cached_profile(self):
        """Load cached profile if exists."""
        profile_path = settings.DATA_DIR / "profile.json"
        if profile_path.exists():
            try:
                with open(profile_path, 'r') as f:
                    data = json.load(f)
                self.profile = UserProfile(**data)
                logger.info(f"Loaded cached profile for: {self.profile.name}")
            except Exception as e:
                logger.warning(f"Could not load cached profile: {e}")

    def extract_text(self, path: str) -> str:
        """Extract text from PDF."""
        text = ""
        try:
            with open(path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
        except Exception as e:
            logger.error(f"Error reading PDF: {e}")
        return text

    def parse_cv(self) -> UserProfile:
        """Parse CV and extract structured profile."""
        cv_text = self.extract_text(settings.CV_PATH)

        if not cv_text.strip():
            raise ValueError("Could not extract text from CV")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a CV parser. Extract information from the CV into JSON.
IMPORTANT: 
- email must be a single string (pick the primary email)
- desired_titles must be a list of job titles
- Be specific about skills

{format_instructions}"""),
            ("human", "Parse this CV:\n\n{cv_text}")
        ])

        logger.info("Parsing CV with Local Ollama...")
        chain = prompt | self.llm | self.parser

        self.profile = chain.invoke({
            "cv_text": cv_text[:4000],
            "format_instructions": self.parser.get_format_instructions()
        })

        # Save profile
        profile_path = settings.DATA_DIR / "profile.json"
        with open(profile_path, 'w') as f:
            json.dump(self.profile.model_dump(), f, indent=2)

        logger.info(f"CV parsed successfully for: {self.profile.name}")
        return self.profile

    def get_profile(self) -> UserProfile:
        """Get profile, parse CV if not cached."""
        if not self.profile:
            self.parse_cv()
        return self.profile
