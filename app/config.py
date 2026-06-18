import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from dotenv import load_dotenv

# Force Python to read the .env file from your project root directory cleanly
load_dotenv()

class Settings(BaseSettings):
    # API Storage Keys
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    
    # Project Identity Settings
    PROJECT_NAME: str = "Celine Esthetique Luxury AI Backend"
    VERSION: str = "1.0.0"
    
    # AI Engine Properties
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()