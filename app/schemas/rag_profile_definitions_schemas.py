from typing import Literal

from sqlmodel import Field, SQLModel


class RagProfileFieldDefinitionRead(SQLModel):
    name: str
    kind: Literal["int", "enum"]
    label: str
    required: bool
    default: int | str
    minimum: int | None = None
    maximum: int | None = None
    help_text: str | None = None
    options: list[str] = Field(default_factory=list)


class RagProfileDefinitionRead(SQLModel):
    strategy: str
    label: str
    fields: list[RagProfileFieldDefinitionRead] = Field(default_factory=list)
