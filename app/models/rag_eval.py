from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime as SQLAlchemyDateTime,
    Index,
    JSON,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .users import User


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RagEvalConfiguration(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, min_length=3)
    chunking: dict = Field(sa_column=Column(JSON, nullable=False))
    rag: dict = Field(sa_column=Column(JSON, nullable=False))
    metrics: dict = Field(sa_column=Column(JSON, nullable=False))
    created_by_user_id: int = Field(foreign_key="user.id")
    last_edit_by_user_id: int | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )
    last_updated: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )

    created_by_user: "User" = Relationship(
        back_populates="rag_eval_configurations_created",
        sa_relationship_kwargs={
            "foreign_keys": "[RagEvalConfiguration.created_by_user_id]"
        },
    )
    last_edit_by_user: Optional["User"] = Relationship(
        back_populates="rag_eval_configurations_last_edited",
        sa_relationship_kwargs={
            "foreign_keys": "[RagEvalConfiguration.last_edit_by_user_id]"
        },
    )
    runs: list["RagEvalRun"] = Relationship(back_populates="configuration")


class RagEvalRun(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_rag_eval_run_valid_status",
        ),
        CheckConstraint(
            "stage IN ("
            "'queued', 'preparing', 'chunking', 'building_index', "
            "'building_graph', 'evaluating', 'scoring', 'cleaning_up', "
            "'persisting', 'finished', 'cleanup_pending'"
            ")",
            name="ck_rag_eval_run_valid_stage",
        ),
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_rag_eval_run_progress_range",
        ),
        CheckConstraint(
            "completed_examples >= 0 AND total_examples >= 0 "
            "AND completed_examples <= total_examples",
            name="ck_rag_eval_run_example_progress",
        ),
        Index(
            "uq_rag_eval_run_global_running",
            "status",
            unique=True,
            postgresql_where=text("status = 'running'"),
            sqlite_where=text("status = 'running'"),
        ),
        Index(
            "ix_rag_eval_run_fifo_queue",
            "queued_at",
            "id",
            postgresql_where=text("status = 'queued'"),
            sqlite_where=text("status = 'queued'"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    configuration_id: int = Field(
        foreign_key="ragevalconfiguration.id",
        index=True,
    )
    status: str = Field(default="queued", index=True, min_length=1)
    stage: str = Field(default="queued", index=True, min_length=1)
    progress: float = Field(default=0.0)
    completed_examples: int = Field(default=0)
    total_examples: int = Field(default=0)
    queued_at: datetime = Field(
        default_factory=_utc_now,
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
    cancel_requested: bool = Field(default=False)
    cancellation_requested_at: datetime | None = Field(
        default=None,
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=True),
    )
    failure_code: str | None = None
    failure_message: str | None = None
    configuration_snapshot: dict = Field(sa_column=Column(JSON, nullable=False))
    suite_version: str = Field(min_length=1)
    suite_content_hash: str = Field(min_length=1)
    resolved_pipeline_snapshot: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    overall_metrics: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    category_metrics: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )

    configuration: "RagEvalConfiguration" = Relationship(back_populates="runs")
    query_results: list["RagEvalQueryResult"] = Relationship(back_populates="run")


class RagEvalQueryResult(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "example_id",
            name="uq_rag_eval_query_result_run_example",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="ragevalrun.id", index=True)
    example_id: str = Field(index=True, min_length=1)
    category: str = Field(index=True, min_length=1)
    answerable: bool
    query: str = Field(min_length=1)
    reference_answer: str | None = None
    actual_answer: str = Field(min_length=1)
    final_chunks: list[dict] = Field(sa_column=Column(JSON, nullable=False))
    first_relevant_rank: int | None = Field(default=None, ge=1)
    hit_at_k: bool | None = None
    mrr_at_k: float | None = Field(default=None, ge=0.0)
    successful_abstention: bool | None = None
    false_positive_context: bool | None = None
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    answer_correctness: float | None = None

    run: "RagEvalRun" = Relationship(back_populates="query_results")
