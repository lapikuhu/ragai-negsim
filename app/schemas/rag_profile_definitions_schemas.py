from typing import Literal

from sqlmodel import Field, SQLModel


class RagProfileFieldDefinitionRead(SQLModel):
    name: str
    kind: Literal["int", "float", "enum"]
    label: str
    required: bool
    default: int | float | str
    minimum: int | float | None = None
    maximum: int | float | None = None
    help_text: str | None = None
    options: list[str] = Field(default_factory=list)


class RagProfileDefinitionRead(SQLModel):
    strategy: str
    label: str
    fields: list[RagProfileFieldDefinitionRead] = Field(default_factory=list)
