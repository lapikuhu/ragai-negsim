from datetime import datetime

from sqlmodel import Field, SQLModel


class IndexedChunkBase(SQLModel):
	corpus_index_id: int
	document_chunk_id: int
	external_vector_id: str | None = Field(default=None, min_length=1)


class IndexedChunkCreate(IndexedChunkBase):
	pass


class IndexedChunkRead(IndexedChunkBase):
	created_at: datetime


class IndexedChunkUpdate(SQLModel):
	external_vector_id: str | None = Field(default=None, min_length=1)


class IndexedChunkDelete(SQLModel):
	corpus_index_id: int
	document_chunk_id: int


class IndexedChunkCreateMany(SQLModel):
	indexed_chunks: list[IndexedChunkCreate] = Field(default_factory=list)


class IndexedChunkVectorRef(SQLModel):
	document_chunk_id: int
	external_vector_id: str | None = Field(default=None, min_length=1)


class IndexedChunkVectorRefsCreate(SQLModel):
	corpus_index_id: int
	chunks: list[IndexedChunkVectorRef] = Field(default_factory=list)
