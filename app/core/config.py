### FastAPI application configuration file

from fastapi import FastAPI
import os
from pathlib import Path
from pydantic_settings import SettingsConfigDict, BaseSettings

env_path = Path(__file__).parent.parent / ".env"

class Settings(BaseSettings):
    # Load environment variables from the .env file
    model_config = SettingsConfigDict(env_file=env_path, env_file_encoding="utf-8")

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    FIXED_ROLES: list[str] = ["admin", "student", "teacher"]
    RAW_DOCS_DIR: str = "app/airag/raw_docs"

settings = Settings()