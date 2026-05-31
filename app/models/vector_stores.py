from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import Column, JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .corpus_indices import CorpusIndex


class VectorStore(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    backend: str
    connection_uri: str | None = None
    collection_name: str | None = None
    table_name: str | None = None
    path: str | None = None
    store_metadata: dict = Field(default_factory=dict, sa_column=Column("metadata", JSON))
    corpus_indices: list["CorpusIndex"] = Relationship(back_populates="vector_store")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
