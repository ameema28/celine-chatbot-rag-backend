from pathlib import Path
from pydantic import Extra
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL_NAME: str = "llama-3.3-70b-versatile"

    FIREBASE_PROJECT_ID: Optional[str] = None
    FIREBASE_SERVICE_ACCOUNT_PATH: Optional[str] = None

    PROJECT_NAME: str = "Celine Esthetique Luxury AI Backend"
    VERSION: str = "1.0.0"
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra=Extra.ignore,
        env_prefix="",
    )

settings = Settings()

# Phase 7: Force environment variable override if present
# This ensures CI secrets always take precedence over .env file
if os.getenv("GROQ_API_KEY"):
    settings.GROQ_API_KEY = os.getenv("GROQ_API_KEY")