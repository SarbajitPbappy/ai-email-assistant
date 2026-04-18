from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from langchain_community.chat_models import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
from src.utils.logger import get_logger
from src.utils.json_parser import extract_json_from_text

logger = get_logger(__name__)


class ReplyDraft(BaseModel):
    subject: str = Field(default="")
    body: str = Field(default="")
    tone: str = Field(default="professional")
    confidence: float = Field(default=0.7)
    requires_human_review: bool = Field(default=True)
    review_reason: str = Field(default="")

    @field_validator('confidence', mode='before')
    @classmethod
    def fix_confidence(cls, v):
        try:
            s = float(v)
            return s / 100 if s > 1.0 else s
        except:
            return 0.7

    @field_validator('requires_human_review', mode='before')
    @classmethod
    def fix_review(cls, v):
        if isinstance(v, str):
            return v.lower() in ['true', 'yes', '1']
        return bool(v)


class ReplyGenerator:
    def __init__(self):
        self.ollama = ChatOllama(
            model="llama3",
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.5
        )
        self.gemini = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=settings.GOOGLE_API_KEY
        )
        self.signature = settings.EMAIL_SIGNATURE

    def _build_prompt(self):
        return ChatPromptTemplate.from_messages([
            ("system", """You write professional email replies for {user_name}.
Output ONLY raw JSON, no markdown, no explanation.

IMPORTANT: 
- Write the body WITHOUT the signature (signature added automatically)
- Be concise, professional, genuine
- Never reveal you are AI
- Write AS {user_name}

Output format:
{{"subject": "Re: ...", "body": "Dear X,\\n\\n<reply body only, NO signature>", "tone": "professional", "confidence": 0.9, "requires_human_review": true, "review_reason": ""}}"""),
            ("human", """Reply to this email:
From: {from_address}
Subject: {subject}
Body: {body}

Category: {category}
{custom_instructions}

Output JSON only:""")
        ])

    def _add_signature(self, body: str) -> str:
        """Add signature to email body."""
        return f"{body}\n\n{self.signature}"

    def generate_reply(
        self,
        email_data: Dict[str, Any],
        classification: Dict[str, Any],
        custom_instructions: str = ""
    ) -> ReplyDraft:
        """Generate reply with signature."""
        body = email_data.get('body_text', '') or email_data.get('snippet', '')
        if len(body) > 1500:
            body = body[:1500]

        chain_input = {
            "user_name": settings.USER_NAME,
            "from_address": email_data.get('from', 'Unknown'),
            "subject": email_data.get('subject', 'No Subject'),
            "body": body,
            "category": classification.get('category', 'other'),
            "custom_instructions": custom_instructions
        }

        prompt = self._build_prompt()

        # Try Ollama first
        try:
            logger.info("Generating reply with Ollama...")
            response = (prompt | self.ollama).invoke(chain_input)
            raw = response.content if hasattr(response, 'content') else str(response)
            data = extract_json_from_text(raw)
            if data and data.get('body'):
                # Add signature
                data['body'] = self._add_signature(data['body'])
                result = ReplyDraft(**data)
                logger.info(f"Reply generated | Confidence: {result.confidence:.0%}")
                return result
            raise ValueError("Empty reply from Ollama")
        except Exception as e:
            logger.warning(f"Ollama reply failed: {e}. Trying Gemini...")

        # Try Gemini
        try:
            response = (prompt | self.gemini).invoke(chain_input)
            raw = response.content if hasattr(response, 'content') else str(response)
            data = extract_json_from_text(raw)
            if data and data.get('body'):
                data['body'] = self._add_signature(data['body'])
                result = ReplyDraft(**data)
                return result
        except Exception as e:
            logger.error(f"Gemini reply failed: {e}")

        # Fallback
        subject = email_data.get('subject', '')
        fallback_body = f"Thank you for your email. I will get back to you shortly."
        return ReplyDraft(
            subject=f"Re: {subject}",
            body=self._add_signature(fallback_body),
            tone="professional",
            confidence=0.3,
            requires_human_review=True,
            review_reason="Auto-generation failed"
        )

    def generate_job_reply(
        self,
        email_data: Dict[str, Any],
        match_result: Any
    ) -> ReplyDraft:
        """Generate reply for job opportunity emails."""
        custom = f"""
This is a JOB OPPORTUNITY email.
Match Score: {match_result.overall_match_score:.0%}
Key matching skills: {', '.join(match_result.matching_skills[:5])}

Write a reply that:
- Expresses genuine interest in the role
- Mentions 2-3 specific matching skills
- Asks about next steps or interview process
- Is under 120 words (excluding signature)
- Is enthusiastic but professional"""

        classification = {
            'category': 'job_opportunity',
            'importance': 'high',
        }
        return self.generate_reply(
            email_data,
            classification,
            custom_instructions=custom
        )
