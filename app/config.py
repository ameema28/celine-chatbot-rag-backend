from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # API Keys
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    
    # Project Metadata
    PROJECT_NAME: str = "Celine AI Backend"
    VERSION: str = "1.0.0"
    
    # AI Models
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"

    # Automatically read from the .env file in the root directory
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Global settings instance
settings = Settings()