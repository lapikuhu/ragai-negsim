from typing import Any, Literal

from sqlmodel import Field, SQLModel


class ChunkerFieldDefinitionRead(SQLModel):
    name: str
    kind: Literal["int", "string", "string_list"]
    label: str
    required: bool
    default: Any
    minimum: int | None = None
    maximum: int | None = None
    help_text: str | None = None


class ChunkerDefinitionRead(SQLModel):
    strategy: str
    label: str
    supports_ingestion: bool
    fields: list[ChunkerFieldDefinitionRead] = Field(default_factory=list)
