from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    GROQ_API_KEY: str | None = None
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

    # Take the client IP for rate limiting from X-Forwarded-For. Only enable behind
    # a reverse proxy that appends the client IP to that header.
    TRUST_PROXY: bool = False
    # Number of trusted proxies that append to X-Forwarded-For. The client IP is
    # the entry this many places from the right (1 = right-most). Entries further
    # left are client-supplied and ignored, so they cannot be used to spoof.
    TRUST_PROXY_HOPS: int = Field(1, ge=1)

    # In-memory session copy (SQLite stays the source of truth): drop sessions unused
    # for this many minutes, and keep at most this many (least recently used first).
    SESSION_TTL_MINUTES: int = Field(60, ge=1)
    SESSION_MEMORY_MAX_SESSIONS: int = Field(1000, ge=1)

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOW_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Environment variables take precedence over values in .env (pydantic-settings default).
settings = Settings()