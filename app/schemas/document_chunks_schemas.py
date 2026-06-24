from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel


class DocumentChunkBase(SQLModel):
	raw_document_id: int
	chunking_profile_id: int
	indexing_job_id: int | None = None
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


class DocumentChunkAdminRead(DocumentChunkBase):
	id: int
	raw_document_name: str | None = None
	chunking_profile_name: str | None = None
	chunking_strategy: str | None = None
	corpus_index_ids: list[int] = Field(default_factory=list)
	indexed_count: int = 0
	is_indexed: bool = False
	created_at: datetime
	last_updated: datetime


class DocumentChunkListResponse(SQLModel):
	items: list[DocumentChunkAdminRead] = Field(default_factory=list)
	skip: int = 0
	limit: int = 20
	total: int = 0
	has_more: bool = False
