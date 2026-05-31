from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import Column, JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .corpus_indices import CorpusIndex
    from .document_chunks import DocumentChunk


class ChunkingProfile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, min_length=3, title="Chunking profile name")
    strategy: str = Field(min_length=1, title="Chunking strategy")
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    document_chunks: list["DocumentChunk"] = Relationship(back_populates="chunking_profile")
    corpus_indices: list["CorpusIndex"] = Relationship(back_populates="chunking_profile")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
