from datetime import datetime

from sqlmodel import Field, SQLModel


class CorpusBm25IndexCreate(SQLModel):
    name: str = Field(min_length=3)
    corpus_id: int
    chunking_profile_id: int
    document_chunk_ids: list[int] = Field(default_factory=list)
    format_version: str = Field(default="pickle-zlib-v1", min_length=1)
    created_by_full_corpus_index_pipe_job_id: int | None = None #Check


class CorpusBm25IndexMetadata(SQLModel):
    id: int
    name: str
    corpus_id: int
    chunking_profile_id: int
    status: str
    format_version: str
    document_count: int
    document_chunk_ids_checksum: str
    compressed_artifact_checksum: str | None = None
    built_at: datetime | None = None
    created_at: datetime
    last_updated: datetime
    build_error: str | None = None
    created_by_full_corpus_index_pipe_job_id: int | None = None #Check
