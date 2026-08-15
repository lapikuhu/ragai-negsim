from datetime import datetime

from sqlmodel import Field, SQLModel


class CorpusChunkSetCreate(SQLModel):
    name: str = Field(min_length=3)
    corpus_id: int
    chunking_profile_id: int
    document_chunk_ids: list[int] = Field(min_length=1)


class CorpusChunkSetUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=3)
    document_chunk_ids: list[int] | None = None
    chunking_profile_name: str | None = Field(default=None, min_length=1)
    chunking_strategy: str | None = Field(default=None, min_length=1)
    chunking_config: dict | None = None


class CorpusChunkSetRead(SQLModel):
    id: int
    corpus_id: int
    name: str
    chunking_profile_id: int | None
    chunking_profile_name: str
    chunking_strategy: str
    chunking_config: dict
    revision: int
    document_chunk_ids_checksum: str
    distinct_document_count: int
    chunk_count: int
    created_at: datetime
    last_updated: datetime


class CorpusChunkSetSnapshot(SQLModel):
    chunk_set: CorpusChunkSetRead
    document_chunk_ids: list[int]


class CorpusChunkSetNameAvailability(SQLModel):
    name: str
    available: bool
    reason: str | None = None
