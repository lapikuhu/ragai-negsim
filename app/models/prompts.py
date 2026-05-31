from sqlmodel import Field, Relationship, SQLModel
from typing import TYPE_CHECKING, Optional, Any
from sqlalchemy import Column, JSON


if TYPE_CHECKING:
    from .users import User

class Prompt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, min_length=3, title="Prompt name")
    description: str | None = None
    messages: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    owner_id: int | None = Field(default=None, foreign_key="user.id")  # None = system default
    owner: Optional["User"] = Relationship(back_populates="prompts")
    is_system: bool = Field(default=False)             # protect built-in prompts