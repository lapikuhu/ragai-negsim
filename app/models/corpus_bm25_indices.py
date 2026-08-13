from datetime import datetime, timezone
from typing import ClassVar

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime as SQLAlchemyDateTime,
    Integer,
    LargeBinary,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import BYTEA
from sqlmodel import Field, SQLModel


class CorpusBm25Index(SQLModel, table=True):
    """A persisted, independently-built BM25 artifact for one corpus snapshot."""

    __tablename__: ClassVar[str] = "corpusbm25index"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'building', 'built', 'failed', 'cancelled', 'retired')",
            name="ck_corpus_bm25_index_valid_status",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, min_length=3)
    corpus_id: int = Field(foreign_key="corpus.id", index=True)
    chunking_profile_id: int = Field(foreign_key="chunkingprofile.id", index=True)
    status: str = Field(
        default="created",
        sa_column=Column(
            String,
            nullable=False,
            index=True,
            server_default=text("'created'"),
        ),
    )
    format_version: str = Field(
        default="pickle-zlib-v1",
        sa_column=Column(
            String,
            nullable=False,
            server_default=text("'pickle-zlib-v1'"),
        ),
    )
    artifact: bytes | None = Field(
        default=None,
        exclude=True,
        repr=False,
        sa_column=Column(
            LargeBinary().with_variant(BYTEA(), "postgresql"),
            nullable=True,
        ),
    )
    document_count: int = Field(
        default=0,
        ge=0,
        sa_column=Column(Integer, nullable=False, server_default=text("0")),
    )
    document_chunk_ids_checksum: str = Field(min_length=64, max_length=64)
    compressed_artifact_checksum: str | None = Field(default=None, min_length=64, max_length=64)
    built_at: datetime | None = Field(
        default=None,
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            SQLAlchemyDateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            SQLAlchemyDateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
    build_error: str | None = None
    created_by_full_corpus_index_pipe_job_id: int | None = Field(
        default=None,
        foreign_key="fullcorpusindexpipejob.id",
    )
    created_by_bm25_build_job_id: int | None = Field(
        default=None,
        foreign_key="corpusbm25buildjob.id",
    )
