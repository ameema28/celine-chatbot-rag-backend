from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL_NAME: str = "openai/gpt-oss-20b"

    PROJECT_NAME: str = "Celine Esthetique Luxury AI Backend"
    VERSION: str = "1.0.0"
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"

    # FAISS relevance cutoff (squared L2 on unit-length embeddings = 2 - 2*cos).
    # Measured: on-topic queries 0.54-0.95, off-topic 1.62-1.87.
    RAG_MAX_L2_DISTANCE: float = 1.20

    # Comma-separated list of browser origins allowed to call the API.
    CORS_ALLOW_ORIGINS: str = (
        "http://localhost:3000,http://localhost:5173,http://localhost:5500,http://127.0.0.1:5500"
    )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOW_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Phase 7: CI/CD fix — environment variables take precedence over .env file
# GitHub Actions injects secrets as env vars; this ensures they are not
# overwritten by an empty or placeholder value in .env
if os.environ.get("GROQ_API_KEY"):
    settings.GROQ_API_KEY = os.environ.get("GROQ_API_KEY")