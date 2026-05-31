from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel


class ChunkingProfileBase(SQLModel):
	name: str = Field(min_length=3, title="Chunking profile name")
	strategy: str = Field(min_length=1, title="Chunking strategy")
	config: dict[str, Any] = Field(default_factory=dict)


class ChunkingProfileCreate(ChunkingProfileBase):
	pass


class ChunkingProfileRead(ChunkingProfileBase):
	id: int
	created_at: datetime
	last_updated: datetime


class ChunkingProfileUpdate(SQLModel):
	name: str | None = Field(default=None, min_length=3, title="Chunking profile name")
	strategy: str | None = Field(default=None, min_length=1, title="Chunking strategy")
	config: dict[str, Any] | None = None


class ChunkingProfileReadWithIds(ChunkingProfileRead):
	document_chunk_ids: list[int] = Field(default_factory=list)
	corpus_index_ids: list[int] = Field(default_factory=list)
