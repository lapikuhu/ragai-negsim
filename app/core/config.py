### FastAPI application configuration file

import os
import warnings
from pathlib import Path
from typing import Annotated, ClassVar

from pydantic import Field
from pydantic_settings import SettingsConfigDict, BaseSettings

from app.core import policies

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
    NEO4J_DATABASE: str = "neo4j"
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: str
    NEO4J_READ_USERNAME: str | None = None
    NEO4J_READ_PASSWORD: str | None = None
    SECRET_KEY: str
    ALGORITHM: ClassVar[str] = policies.ALGORITHM
    OPENAI_API_KEY: str
    OPENAI_CHAT_MODELS: ClassVar[tuple[str, ...]] = policies.OPENAI_CHAT_MODELS
    OPEN_AI_DEFAULT_MODEL: ClassVar[str] = policies.OPEN_AI_DEFAULT_MODEL
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_DEFAULT_MODEL: ClassVar[str] = policies.OLLAMA_DEFAULT_MODEL
    ACCESS_TOKEN_EXPIRE_MINUTES: ClassVar[int] = policies.ACCESS_TOKEN_EXPIRE_MINUTES
    FIXED_ROLES: ClassVar[tuple[str, ...]] = policies.FIXED_ROLES
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
    LANGSMITH_API_KEY: str | None = None
    LANGSMITH_TRACING: bool = False
    LANGSMITH_PROJECT: str | None = None
    LANGSMITH_ENDPOINT: str | None = None
    COHERE_API_KEY: str | None = None
    HF_TOKEN: str | None = None
    TAVILY_API_KEY: str | None = None
    MAX_UPLOAD_SIZE: ClassVar[int] = policies.MAX_UPLOAD_SIZE
    RAG_EVAL_EMBEDDING_CACHE_ENABLED: bool = True
    REDIS_URL: str = "redis://localhost:6379/0"
    RAG_EVAL_EMBEDDING_CACHE_TTL_SECONDS: Annotated[int, Field(gt=0)] = 86400


def _set_or_clear_env(name: str, value: str | None) -> None:
    """
    Set or clear an environment variable based on the provided value.
    If the value is not None, the environment variable with the given name
    will be set to the value. If the value is None, the environment variable
    will be removed from the environment.

    Args:
        name (str): The name of the environment variable to set or clear.
        value (str | None): The value to set for the environment variable. 
        If None, the variable will be removed.
    Returns:
        None
    """
    if value:
        os.environ[name] = value
    else:
        os.environ.pop(name, None)


def configure_langsmith_environment(settings: Settings) -> None:
    """
    Configure the environment variables for LangSmith based on the provided 
    settings. LangSmith reads its configuration from environment variables, 
    so this function sets or clears the relevant environment variables 
    accordingly. It bridges the gap between the application's settings and 
    LangSmith's expected environment configuration.
    """
    _set_or_clear_env("LANGSMITH_API_KEY", settings.LANGSMITH_API_KEY)
    _set_or_clear_env("LANGSMITH_PROJECT", settings.LANGSMITH_PROJECT)
    _set_or_clear_env("LANGSMITH_ENDPOINT", settings.LANGSMITH_ENDPOINT)

    tracing_enabled = "true" if settings.LANGSMITH_TRACING else "false"
    os.environ["LANGSMITH_TRACING"] = tracing_enabled
    os.environ["LANGSMITH_TRACING_V2"] = tracing_enabled

    if settings.LANGSMITH_TRACING and not settings.LANGSMITH_API_KEY:
        warnings.warn(
            "LangSmith tracing is enabled but LANGSMITH_API_KEY is missing.",
            RuntimeWarning,
            stacklevel=2,
        )

settings = Settings()
# Give LangSmith the environment variables it expects, based on our settings
configure_langsmith_environment(settings)
