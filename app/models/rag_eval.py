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
    from .chunking_profiles import ChunkingProfile
    from .rag_profiles import RagProfile
    from .users import User


class RagEvalPairProfile(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "rag_profile_id",
            "chunking_profile_id",
            name="uq_rag_eval_pair_rag_chunking",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, min_length=3)
    rag_profile_id: int = Field(foreign_key="ragprofile.id", index=True)
    chunking_profile_id: int = Field(foreign_key="chunkingprofile.id", index=True)
    created_by_user_id: int = Field(foreign_key="user.id")
    last_edit_by_user_id: int | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )

    rag_profile: "RagProfile" = Relationship(back_populates="rag_eval_pair_profiles")
    chunking_profile: "ChunkingProfile" = Relationship(
        back_populates="rag_eval_pair_profiles"
    )
    created_by_user: "User" = Relationship(
        back_populates="rag_eval_pair_profiles_created",
        sa_relationship_kwargs={"foreign_keys": "[RagEvalPairProfile.created_by_user_id]"},
    )
    last_edit_by_user: Optional["User"] = Relationship(
        back_populates="rag_eval_pair_profiles_last_edited",
        sa_relationship_kwargs={"foreign_keys": "[RagEvalPairProfile.last_edit_by_user_id]"},
    )
    runs: list["RagEvalRun"] = Relationship(back_populates="pair_profile")


class RagEvalRun(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_rag_eval_run_valid_status",
        ),
        Index(
            "uq_rag_eval_run_active_pair",
            "pair_profile_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    pair_profile_id: int = Field(foreign_key="ragevalpairprofile.id", index=True)
    status: str = Field(default="queued", index=True, min_length=1)
    stage: str = Field(default="queued", index=True, min_length=1)
    cancel_requested: bool = Field(default=False)
    failure_detail: str | None = None
    k: int = Field(ge=1)
    rag_profile_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON))
    chunking_profile_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON))
    evaluation_model_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON))
    aggregate_hit_rate_at_k: float | None = None
    aggregate_mrr_at_k: float | None = None
    aggregate_ragas_metrics: dict = Field(default_factory=dict, sa_column=Column(JSON))
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

    pair_profile: "RagEvalPairProfile" = Relationship(back_populates="runs")
    query_results: list["RagEvalQueryResult"] = Relationship(back_populates="run")


class RagEvalQueryResult(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="ragevalrun.id", index=True)
    evaluation_id: str = Field(index=True, min_length=1)
    query: str = Field(min_length=1)
    reference_answer: str | None = None
    answer: str | None = None
    retrieved_contexts: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    retrieved_evaluation_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    reference_rank: int | None = Field(default=None, ge=1)
    hit_at_k: bool = Field(default=False)
    mrr_contribution: float = Field(default=0.0, ge=0.0)
    ragas_metrics: dict = Field(default_factory=dict, sa_column=Column(JSON))

    run: "RagEvalRun" = Relationship(back_populates="query_results")
