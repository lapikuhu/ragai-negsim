from sqlmodel import Field, SQLModel
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

class Prompt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)         # e.g. "doc_grade"
    description: str | None = None
    messages: dict = Field(sa_column=Column(JSONB, nullable=False))
    owner_id: int | None = Field(default=None, foreign_key="user.id")  # None = system default
    is_system: bool = Field(default=False)             # protect built-in prompts