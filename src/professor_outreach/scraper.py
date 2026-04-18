import requests
import re
from bs4 import BeautifulSoup
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
from src.utils.logger import get_logger
from src.utils.json_parser import extract_json_from_text

logger = get_logger(__name__)

GOOGLE_SCHOLAR_DOMAINS = ['scholar.google.com', 'scholar.google.']


class ProfessorScraper:
    """
    Smart professor data extractor.
    Handles: text, university URLs, mixed content.
    For Google Scholar: asks user to paste content manually.
    """

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                         'AppleWebKit/537.36'
        }
        self.llm = ChatOllama(
            model="llama3",
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.1
        )

    def extract(self, raw_input: str) -> dict:
        """
        Smart extraction from ANY input.
        Returns dict with 'needs_more_info' flag if Scholar URL detected.
        """
        raw_input = raw_input.strip()
        collected_text = raw_input

        # Find URLs
        urls = re.findall(r'https?://[^\s]+', raw_input)
        scraped_contents = []
        scholar_urls = []

        for url in urls:
            # Check if Google Scholar
            if any(domain in url for domain in GOOGLE_SCHOLAR_DOMAINS):
                scholar_urls.append(url)
                logger.info(f"Google Scholar URL detected: {url}")
                continue

            # Try scraping other URLs
            logger.info(f"Scraping URL: {url}")
            content = self._scrape_url(url)
            if content and len(content) > 200:
                scraped_contents.append(content)
                logger.info(f"Scraped {len(content)} chars from {url}")
            else:
                logger.warning(f"Could not scrape useful content from {url}")

        # If only Google Scholar URL and nothing else
        if scholar_urls and not scraped_contents and raw_input.strip() in scholar_urls:
            return {
                "needs_more_info": True,
                "scholar_url": scholar_urls[0],
                "name": "",
                "university": "",
                "department": "",
                "email": "",
                "research_interests": [],
                "recent_papers": [],
                "research_summary": "",
                "position": "",
                "raw_content": raw_input
            }

        # Combine all content
        if scraped_contents:
            collected_text = raw_input + "\n\n" + "\n\n".join(scraped_contents)

        # Use AI to extract structured info
        profile = self._ai_extract(collected_text)
        profile["needs_more_info"] = False
        return profile

    def _scrape_url(self, url: str) -> str:
        """Scrape raw text from any non-Scholar URL."""
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=15
            )
            soup = BeautifulSoup(response.text, 'html.parser')

            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            text = soup.get_text(separator=" ", strip=True)
            text = re.sub(r'\s+', ' ', text)

            # Check if useful content
            if len(text) < 100 or "page not found" in text.lower():
                return ""

            return text[:4000]

        except Exception as e:
            logger.warning(f"Could not scrape {url}: {e}")
            return ""

    def _ai_extract(self, raw_content: str) -> dict:
        """Use AI to extract professor info from any raw content."""

        prompt = ChatPromptTemplate.from_messages([
            ("system", "Extract professor information from content. "
                      "Output ONLY raw JSON no markdown."),
            ("human", """Extract professor info from this:

{content}

Return ONLY this JSON:
{{
  "name": "professor full name or empty",
  "university": "university name or empty",
  "department": "department or empty",
  "email": "email or empty",
  "position": "Professor/Associate Professor etc or empty",
  "research_interests": ["interest 1", "interest 2"],
  "recent_papers": [
    {{"title": "paper title", "journal": "journal", "year": "2024"}}
  ],
  "research_summary": "2-3 sentence summary of research focus"
}}
""")
        ])

        try:
            response = (prompt | self.llm).invoke({
                "content": raw_content[:3500]
            })
            data = extract_json_from_text(response.content)
            if data:
                data["raw_content"] = raw_content[:3000]
                return data
        except Exception as e:
            logger.error(f"AI extraction error: {e}")

        return self._basic_extract(raw_content)

    def _basic_extract(self, text: str) -> dict:
        """Basic regex fallback."""
        profile = {
            "name": "",
            "university": "",
            "department": "",
            "email": "",
            "research_interests": [],
            "recent_papers": [],
            "research_summary": text[:500],
            "position": "",
            "raw_content": text[:3000],
            "needs_more_info": False
        }

        emails = re.findall(
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            text
        )
        skip = ['noreply', 'example', 'info@', 'admin@', 'support@']
        for email in emails:
            if not any(s in email for s in skip):
                profile["email"] = email
                break

        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            lower = line.lower()
            if lower.startswith("name:"):
                profile["name"] = line.split(":", 1)[1].strip()
            elif lower.startswith("university:"):
                profile["university"] = line.split(":", 1)[1].strip()
            elif lower.startswith("email:"):
                profile["email"] = line.split(":", 1)[1].strip()
            elif lower.startswith("department:"):
                profile["department"] = line.split(":", 1)[1].strip()

        return profile
