from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = Path(__file__).parent.parent / "data"
    LOG_DIR: Path = Path(__file__).parent.parent / "logs"

    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "llama3"
    GOOGLE_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    PRIMARY_LLM: str = "ollama"
    BACKUP_LLM: str = "gemini"

    GMAIL_CREDENTIALS_FILE: str = "config/credentials.json"
    GMAIL_TOKEN_FILE: str = "config/token.json"

    CV_PATH: str = "data/my_cv.pdf"
    RESEARCH_PROFILE_PATH: str = "data/research_profile.json"
    USER_NAME: str = "Sarbajit Paul Bappy"
    USER_EMAIL: str = ""

    EMAIL_SIGNATURE: str = ""
    MIN_MATCH_SCORE: float = 0.70
    AUTO_APPLY_ENABLED: bool = False
    MAX_DAILY_APPLICATIONS: int = 10
    AUTO_REPLY_ENABLED: bool = False
    REPLY_REVIEW_MODE: bool = True

    FIREBASE_KEY_PATH: str = "config/firebase_key.json"

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    EMAIL_CHECK_INTERVAL_MINUTES: int = 15

    class Config:
        env_file = "config/.env"
        extra = "allow"

settings = Settings()
