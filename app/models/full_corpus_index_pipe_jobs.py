from datetime import datetime, timezone
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import Column, DateTime as SQLAlchemyDateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .corpus_indices import CorpusIndex
    from .document_chunks import DocumentChunk
    from .full_corpus_index_pipe_job_warnings import FullCorpusIndexPipeJobWarning
    from .raw_documents import RawDocument

# Model for tracking the progress and details of a full corpus index pipe job.
# These jobs can take time, so we need to track them.

class FullCorpusIndexPipeJob(SQLModel, table=True):
    __tablename__: ClassVar[str] = "fullcorpusindexpipejob"

    id: int | None = Field(default=None, primary_key=True)
    corpus_id: int = Field(foreign_key="corpus.id", index=True)
    chunking_profile_id: int = Field(foreign_key="chunkingprofile.id")
    vector_store_id: int = Field(foreign_key="vectorstore.id")
    embedding_model: str = Field(min_length=1)
    requested_index_name: str = Field(min_length=3)
    requested_chunk_set_name: str = Field(min_length=3)
    requested_vector_namespace: str | None = None
    build_bm25: bool = Field(default=True)
    requested_bm25_index_name: str | None = Field(default=None, min_length=3)
    requested_by_user_id: int | None = Field(default=None, foreign_key="user.id")
    bm25_build_job_id: int | None = Field(
        default=None,
        foreign_key="corpusbm25buildjob.id",
    )
    corpus_chunk_set_id: int | None = Field(
        default=None,
        foreign_key="corpuschunkset.id",
        index=True,
        ondelete="SET NULL",
    )
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
        sa_relationship_kwargs={"foreign_keys": "[FullCorpusIndexPipeJob.candidate_corpus_index_id]"}
    )
    replaced_corpus_index: "CorpusIndex" = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[FullCorpusIndexPipeJob.replaced_corpus_index_id]"}
    )
    document_chunks: list["DocumentChunk"] = Relationship(back_populates="full_corpus_index_pipe_job")
    warnings: list["FullCorpusIndexPipeJobWarning"] = Relationship(back_populates="full_corpus_index_pipe_job")
