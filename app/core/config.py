### FastAPI application configuration file

from pathlib import Path
from pydantic_settings import SettingsConfigDict, BaseSettings

env_path = Path(__file__).parent.parent.parent / ".env"

class Settings(BaseSettings):
    # Load environment variables from the .env file
    model_config = SettingsConfigDict(env_file=env_path, 
                                      env_file_encoding="utf-8",
                                      extra="ignore")

    ASYNC_DATABASE_URL: str
    ADMIN_USERNAME: str
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    NEO4J_URI: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: str
    NEO4J_READ_USERNAME: str | None = None
    NEO4J_READ_PASSWORD: str | None = None
    SECRET_KEY: str
    ALGORITHM: str
    OPENAI_API_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    FIXED_ROLES: list[str] = ["admin", "student", "teacher"]
    RAW_DOCS_DIR: str = "app/raw_docs_store"
    CORS_ALLOW_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    HF_TOKEN: str

settings = Settings()
