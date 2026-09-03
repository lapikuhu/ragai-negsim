"""
Policies and configuration constants for the application. These are
separate from environmental variables, but both assemble in config.py
for the application's core configuration.
"""

from typing import Final


OPENAI_CHAT_MODELS: Final[tuple[str, ...]] = (
    "gpt-4o-mini",
    "gpt-4.1-mini",
    "gpt-4.1",
    "o3",
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.2",
    "gpt-5.1",
    "gpt-5",
    "gpt-5-mini",
)
OPEN_AI_DEFAULT_MODEL: Final[str] = "gpt-4o-mini"
OLLAMA_DEFAULT_MODEL: Final[str] = "qwen2.5:1.5b-instruct"
ALGORITHM: Final[str] = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = 360
FIXED_ROLES: Final[tuple[str, ...]] = ("admin", "student", "teacher")
MAX_UPLOAD_SIZE: Final[int] = 248 * 1024 * 1024
