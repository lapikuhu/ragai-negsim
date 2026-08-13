from datetime import datetime, timezone
from typing import ClassVar

from sqlalchemy import CheckConstraint, Column, DateTime, JSON
from sqlmodel import Field, SQLModel


class CorpusBm25BuildJob(SQLModel, table=True):
    __tablename__: ClassVar[str] = "corpusbm25buildjob"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_corpus_bm25_build_job_valid_status",
        ),
        CheckConstraint(
            "stage IN ('queued', 'validating_snapshot', 'building_artifact', "
            "'persisting_artifact', 'finished')",
            name="ck_corpus_bm25_build_job_valid_stage",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    requested_artifact_name: str = Field(min_length=3)
    corpus_id: int = Field(foreign_key="corpus.id", index=True)
    chunking_profile_id: int = Field(foreign_key="chunkingprofile.id", index=True)
    requested_by_user_id: int = Field(foreign_key="user.id")
    document_chunk_ids: list[int] = Field(sa_column=Column(JSON, nullable=False))
    document_chunk_ids_checksum: str = Field(min_length=64, max_length=64)
    distinct_document_count: int = Field(ge=0)
    chunk_count: int = Field(ge=1)
    status: str = Field(default="queued", index=True)
    stage: str = Field(default="queued", index=True)
    cancel_requested: bool = Field(default=False)
    queued_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    result_bm25_index_id: int | None = Field(default=None, foreign_key="corpusbm25index.id")
    failure_detail: str | None = None
