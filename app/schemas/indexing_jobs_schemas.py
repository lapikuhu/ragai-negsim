from datetime import datetime

from sqlmodel import Field, SQLModel


class IndexingJobBase(SQLModel):
    corpus_id: int
    chunking_profile_id: int
    vector_store_id: int
    embedding_model: str = Field(min_length=1)
    requested_index_name: str = Field(min_length=3)
    requested_vector_namespace: str | None = None


class IndexingJobCreate(IndexingJobBase):
    status: str = Field(default="queued", min_length=1)
    stage: str = Field(default="validating", min_length=1)


class IndexingJobWarningRead(SQLModel):
    id: int
    raw_document_id: int | None = None
    document_name: str | None = None
    stage: str
    message: str
    created_at: datetime


class IndexingJobRead(IndexingJobBase):
    id: int
    status: str
    stage: str
    current_raw_document_id: int | None = None
    current_document_name: str | None = None
    total_documents: int
    processed_documents: int
    chunks_created: int
    chunks_indexed: int
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    candidate_corpus_index_id: int | None = None
    replaced_corpus_index_id: int | None = None
    failure_detail: str | None = None


class IndexingJobQueued(IndexingJobRead):
    pass


class IndexingJobDetail(IndexingJobRead):
    warnings: list[IndexingJobWarningRead] = Field(default_factory=list)
