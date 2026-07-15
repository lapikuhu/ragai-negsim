from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel


class RagEvalPairProfileBase(SQLModel):
    name: str = Field(min_length=3)
    rag_profile_id: int
    chunking_profile_id: int


class RagEvalPairProfileCreateRequest(RagEvalPairProfileBase):
    pass


class RagEvalPairProfileCreate(RagEvalPairProfileBase):
    created_by_user_id: int


class RagEvalPairProfileUpdateRequest(SQLModel):
    name: str | None = Field(default=None, min_length=3)


class RagEvalPairProfileUpdate(RagEvalPairProfileUpdateRequest):
    last_edit_by_user_id: int | None = None


class RagEvalPairProfileRead(RagEvalPairProfileBase):
    id: int
    created_by_user_id: int
    last_edit_by_user_id: int | None = None
    created_at: datetime
    last_updated: datetime


class RagEvalRunCreate(SQLModel):
    pair_profile_id: int
    k: int = Field(ge=1)
    rag_profile_snapshot: dict[str, Any] = Field(default_factory=dict)
    chunking_profile_snapshot: dict[str, Any] = Field(default_factory=dict)
    evaluation_model_snapshot: dict[str, Any] = Field(default_factory=dict)


class RagEvalRunStartRequest(SQLModel):
    k: int = Field(default=4, ge=1)
    llm_provider: str
    llm_model: str
    embedding_model: str


class RagEvalQueryResultCreate(SQLModel):
    run_id: int
    evaluation_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    reference_answer: str | None = None
    answer: str | None = None
    retrieved_contexts: list[str] = Field(default_factory=list)
    retrieved_evaluation_ids: list[str] = Field(default_factory=list)
    reference_rank: int | None = Field(default=None, ge=1)
    hit_at_k: bool = False
    mrr_contribution: float = Field(default=0.0, ge=0.0)
    ragas_metrics: dict[str, Any] = Field(default_factory=dict)


class RagEvalQueryResultRead(RagEvalQueryResultCreate):
    id: int


class RagEvalRunRead(SQLModel):
    id: int
    pair_profile_id: int
    status: str
    stage: str
    cancel_requested: bool
    failure_detail: str | None = None
    k: int
    rag_profile_snapshot: dict[str, Any]
    chunking_profile_snapshot: dict[str, Any]
    evaluation_model_snapshot: dict[str, Any]
    aggregate_hit_rate_at_k: float | None = None
    aggregate_mrr_at_k: float | None = None
    aggregate_ragas_metrics: dict[str, Any]
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RagEvalRunDetailRead(RagEvalRunRead):
    query_results: list[RagEvalQueryResultRead] = Field(default_factory=list)
