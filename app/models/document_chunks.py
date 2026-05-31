from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import Column, JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .chunking_profiles import ChunkingProfile
    from .indexed_chunks import IndexedChunk
    from .raw_documents import RawDocument


class DocumentChunk(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    raw_document_id: int = Field(foreign_key="rawdocument.id")
    chunking_profile_id: int = Field(foreign_key="chunkingprofile.id")
    chunk_index: int = Field(ge=0)
    content: str = Field(min_length=1, title="Chunk content")
    chunk_metadata: dict = Field(default_factory=dict, sa_column=Column("metadata", JSON))
    raw_document: "RawDocument" = Relationship(back_populates="document_chunks")
    chunking_profile: "ChunkingProfile" = Relationship(back_populates="document_chunks")
    indexed_chunks: list["IndexedChunk"] = Relationship(back_populates="document_chunk")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
