from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel


class DocumentChunkBase(SQLModel):
	raw_document_id: int
	chunking_profile_id: int
	chunk_index: int = Field(ge=0)
	chunk_metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentChunkCreate(DocumentChunkBase):
	content: str = Field(min_length=1, title="Chunk content")


class DocumentChunkRead(DocumentChunkBase):
	id: int
	created_at: datetime
	last_updated: datetime


class DocumentChunkReadWithContent(DocumentChunkRead):
	content: str


class DocumentChunkUpdate(SQLModel):
	chunk_index: int | None = Field(default=None, ge=0)
	content: str | None = Field(default=None, min_length=1, title="Chunk content")
	chunk_metadata: dict[str, Any] | None = None


class DocumentChunkReadWithIds(DocumentChunkRead):
	corpus_index_ids: list[int] = Field(default_factory=list)


class DocumentChunkIndexedChunkRead(SQLModel):
	corpus_index_id: int
	external_vector_id: str | None = None
	created_at: datetime


class DocumentChunkReadWithIndexedChunks(DocumentChunkRead):
	indexed_chunks: list[DocumentChunkIndexedChunkRead] = Field(default_factory=list)
