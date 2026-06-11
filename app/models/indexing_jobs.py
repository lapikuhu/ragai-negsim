from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime as SQLAlchemyDateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .corpus_indices import CorpusIndex
    from .document_chunks import DocumentChunk
    from .indexing_job_warnings import IndexingJobWarning
    from .raw_documents import RawDocument

# Model for tracking the progress and details of an indexing job.
# Indexing jobs can take time, so we need to track them.

class IndexingJob(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    corpus_id: int = Field(foreign_key="corpus.id", index=True)
    chunking_profile_id: int = Field(foreign_key="chunkingprofile.id")
    vector_store_id: int = Field(foreign_key="vectorstore.id")
    embedding_model: str = Field(min_length=1)
    requested_index_name: str = Field(min_length=3)
    requested_vector_namespace: str | None = None
    status: str = Field(index=True, min_length=1)
    stage: str = Field(index=True, min_length=1)
    current_raw_document_id: int | None = Field(default=None, foreign_key="rawdocument.id")
    current_document_name: str | None = None
    total_documents: int = Field(default=0, ge=0)
    processed_documents: int = Field(default=0, ge=0)
    chunks_created: int = Field(default=0, ge=0)
    chunks_indexed: int = Field(default=0, ge=0)
    cancel_requested: bool = Field(default=False)
    queued_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )
    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=True),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=True),
    )
    candidate_corpus_index_id: int | None = Field(default=None, foreign_key="corpusindex.id")
    replaced_corpus_index_id: int | None = Field(default=None, foreign_key="corpusindex.id")
    failure_detail: str | None = None
    current_raw_document: "RawDocument" = Relationship()
    candidate_corpus_index: "CorpusIndex" = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[IndexingJob.candidate_corpus_index_id]"}
    )
    replaced_corpus_index: "CorpusIndex" = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[IndexingJob.replaced_corpus_index_id]"}
    )
    document_chunks: list["DocumentChunk"] = Relationship(back_populates="indexing_job")
    warnings: list["IndexingJobWarning"] = Relationship(back_populates="indexing_job")
