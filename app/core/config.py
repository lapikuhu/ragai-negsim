### FastAPI application configuration file

from fastapi import FastAPI
import os
from pathlib import Path
from pydantic_settings import SettingsConfigDict, BaseSettings

env_path = Path(__file__).parent.parent.parent / ".env"

class Settings(BaseSettings):
    # Load environment variables from the .env file
    model_config = SettingsConfigDict(env_file=env_path, 
                                      env_file_encoding="utf-8",
                                      extra="ignore")

    ASYNC_DATABASE_URL: str
    NEO4J_URI: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: str
    SECRET_KEY: str
    ALGORITHM: str
    OPENAI_API_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    FIXED_ROLES: list[str] = ["admin", "student", "teacher"]
    RAW_DOCS_DIR: str = "app/airag/raw_docs"
    HF_TOKEN: str

settings = Settings()