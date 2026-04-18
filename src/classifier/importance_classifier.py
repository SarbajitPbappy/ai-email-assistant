from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain_community.chat_models import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

class EmailClassification(BaseModel):
    category: str = Field(description="job_opportunity, networking, newsletter, personal, spam, other")
    importance: str = Field(description="critical, high, medium, low, ignore")
    is_job_related: bool = Field(description="True/False")
    needs_reply: bool = Field(description="True/False")
    summary: str = Field(description="1-2 sentence summary")
    key_action_items: List[str] = Field(description="List of tasks")
    confidence_score: float = Field(description="0.0 to 1.0")

class EmailClassifier:
    def __init__(self):
        # Primary: Local Ollama (Unlimited)
        self.ollama_llm = ChatOllama(model="llama3", base_url=settings.OLLAMA_BASE_URL)
        
        # Backup: Google Gemini (Free API)
        self.gemini_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=settings.GOOGLE_API_KEY)
        
        self.parser = PydanticOutputParser(pydantic_object=EmailClassification)

    def classify(self, email_data: Dict[str, Any]) -> EmailClassification:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an AI email assistant. Classify this email for {user_name}.\n{format_instructions}"),
            ("human", "Subject: {subject}\nFrom: {from_address}\nBody: {body}")
        ])
        
        chain_input = {
            "user_name": settings.USER_NAME,
            "subject": email_data.get('subject', 'No Subject'),
            "from_address": email_data.get('from', 'Unknown'),
            "body": (email_data.get('body_text') or email_data.get('snippet'))[:2000],
            "format_instructions": self.parser.get_format_instructions()
        }

        # Try Local Ollama first
        try:
            logger.info("Attempting classification with Local Ollama...")
            response = (prompt | self.ollama_llm | self.parser).invoke(chain_input)
            return response
        except Exception as e:
            logger.warning(f"Ollama failed or not running: {e}. Switching to Gemini...")
            # Fallback to Gemini
            try:
                response = (prompt | self.gemini_llm | self.parser).invoke(chain_input)
                return response
            except Exception as e2:
                logger.error(f"Both LLMs failed: {e2}")
                return EmailClassification(category="other", importance="medium", is_job_related=False, needs_reply=False, summary="Error", key_action_items=[], confidence_score=0)
