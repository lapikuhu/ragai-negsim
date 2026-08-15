from datetime import datetime

from pydantic import model_validator
from sqlmodel import Field, SQLModel


class FullCorpusIndexPipeJobBase(SQLModel):
    corpus_id: int
    chunking_profile_id: int
    vector_store_id: int
    embedding_model: str = Field(min_length=1)
    requested_index_name: str = Field(min_length=3)
    requested_chunk_set_name: str = Field(min_length=3)
    requested_vector_namespace: str | None = None
    build_bm25: bool = True
    requested_bm25_index_name: str | None = Field(default=None, min_length=3)


class FullCorpusIndexPipeJobCreate(FullCorpusIndexPipeJobBase):
    status: str = Field(default="queued", min_length=1)
    stage: str = Field(default="validating", min_length=1)

    @model_validator(mode="after")
    def validate_bm25_request(self):
        """
        Validate that if BM25 building is requested, a valid BM25 index name 
        is provided.
        """
        if not self.build_bm25:
            self.requested_bm25_index_name = None
            return self
        name = (self.requested_bm25_index_name or "").strip()
        if len(name) < 3:
            raise ValueError("BM25 index name is required when BM25 building is enabled")
        self.requested_bm25_index_name = name
        return self


class FullCorpusIndexPipeJobPersist(FullCorpusIndexPipeJobCreate):
    requested_by_user_id: int


class FullCorpusIndexPipeJobWarningRead(SQLModel):
    id: int
    raw_document_id: int | None = None
    document_name: str | None = None
    stage: str
    message: str
    created_at: datetime


class FullCorpusIndexPipeJobRead(FullCorpusIndexPipeJobBase):
    id: int
    status: str
    stage: str
    cancel_requested: bool = False
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
    requested_by_user_id: int | None = None
    bm25_build_job_id: int | None = None
    corpus_chunk_set_id: int | None = None
    failure_detail: str | None = None


class FullCorpusIndexPipeJobQueued(FullCorpusIndexPipeJobRead):
    pass


class FullCorpusIndexPipeJobDetail(FullCorpusIndexPipeJobRead):
    warnings: list[FullCorpusIndexPipeJobWarningRead] = Field(default_factory=list)
