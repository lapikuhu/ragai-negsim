from datetime import datetime

from sqlmodel import Field, SQLModel


class CorpusIndexBase(SQLModel):
    name: str = Field(min_length=3, title="Corpus index name")
    embedding_model: str = Field(min_length=1, title="Embedding model")
    embedding_dimensions: int | None = Field(default=None, ge=1)
    vector_namespace: str | None = None


class CorpusIndexCreate(CorpusIndexBase):
    corpus_id: int
    vector_store_id: int
    chunking_profile_id: int
    status: str = Field(default="created", min_length=1, title="Corpus index status")


class CorpusIndexRead(CorpusIndexBase):
    id: int
    corpus_id: int
    vector_store_id: int
    chunking_profile_id: int
    status: str
    built_at: datetime | None = None
    created_at: datetime
    last_updated: datetime


class CorpusIndexUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="Corpus index name")
    status: str | None = Field(default=None, min_length=1, title="Corpus index status")
    embedding_model: str | None = Field(default=None, min_length=1, title="Embedding model")
    embedding_dimensions: int | None = Field(default=None, ge=1)
    vector_namespace: str | None = None
    built_at: datetime | None = None


class CorpusIndexStatusUpdate(SQLModel):
    status: str = Field(min_length=1, title="Corpus index status")


class CorpusIndexBuildComplete(SQLModel):
    status: str = Field(default="built", min_length=1, title="Corpus index status")
    built_at: datetime
    embedding_dimensions: int | None = Field(default=None, ge=1)
    vector_namespace: str | None = None


class CorpusIndexCopy(SQLModel):
    name: str = Field(min_length=3, title="Corpus index name")
    corpus_id: int | None = None
    vector_store_id: int | None = None
    chunking_profile_id: int | None = None
    embedding_model: str | None = Field(default=None, min_length=1, title="Embedding model")
    embedding_dimensions: int | None = Field(default=None, ge=1)
    vector_namespace: str | None = None


class CorpusIndexReadWithIds(CorpusIndexRead):
    indexed_document_chunk_ids: list[int] = Field(default_factory=list)

class CorpusIndexIndexedChunkRead(SQLModel):
    document_chunk_id: int
    external_vector_id: str | None = None
    created_at: datetime


class CorpusIndexReadWithIndexedChunks(CorpusIndexRead):
    indexed_chunks: list[CorpusIndexIndexedChunkRead] = Field(default_factory=list)