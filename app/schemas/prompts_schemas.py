from typing import Any

from sqlmodel import Field, SQLModel


class PromptBase(SQLModel):
    name: str = Field(min_length=3, title="Prompt name")
    description: str | None = None
    messages: dict[str, Any] = Field(default_factory=dict)


class PromptCreate(PromptBase):
    owner_id: int | None = None
    is_system: bool = False


class PromptRead(PromptBase):
    id: int
    owner_id: int | None = None
    is_system: bool


class PromptUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="Prompt name")
    description: str | None = None
    messages: dict[str, Any] | None = None


class PromptAdminUpdate(PromptUpdate):
    owner_id: int | None = None
    is_system: bool | None = None


class PromptClone(SQLModel):
    name: str = Field(min_length=3, title="Prompt name")
    owner_id: int
    description: str | None = None