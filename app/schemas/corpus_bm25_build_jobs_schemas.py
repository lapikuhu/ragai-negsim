from datetime import datetime

from sqlmodel import Field, SQLModel


class CorpusBm25BuildJobQueueRequest(SQLModel):
    requested_artifact_name: str = Field(min_length=3)
    corpus_chunk_set_id: int


class CorpusBm25BuildJobRetryRequest(SQLModel):
    requested_artifact_name: str = Field(min_length=3)


class CorpusBm25BuildJobCreate(SQLModel):
    requested_artifact_name: str = Field(min_length=3)
    corpus_id: int
    chunking_profile_id: int
    corpus_chunk_set_id: int
    corpus_chunk_set_revision: int = Field(ge=1)
    corpus_chunk_set_checksum: str = Field(min_length=64, max_length=64)
    requested_by_user_id: int
    document_chunk_ids: list[int]
    document_chunk_ids_checksum: str = Field(min_length=64, max_length=64)
    distinct_document_count: int = Field(ge=0)
    chunk_count: int = Field(ge=1)
    status: str = "queued"
    stage: str = "queued"


class CorpusBm25BuildJobRead(SQLModel):
    id: int
    requested_artifact_name: str
    corpus_id: int
    chunking_profile_id: int
    corpus_chunk_set_id: int | None
    corpus_chunk_set_revision: int
    corpus_chunk_set_checksum: str
    requested_by_user_id: int
    document_chunk_ids_checksum: str
    distinct_document_count: int
    chunk_count: int
    status: str
    stage: str
    cancel_requested: bool
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_bm25_index_id: int | None = None
    failure_detail: str | None = None


class CorpusBm25IndexNameAvailability(SQLModel):
    name: str
    available: bool
    reason: str | None = None
