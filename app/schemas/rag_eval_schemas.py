from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel


class RagEvalGraphBuildConfig(SQLModel):
    llm_provider: str = Field(min_length=1)
    llm_model: str = Field(min_length=1)
    max_paths_per_chunk: int = Field(ge=1)


class RagEvalRetrievalConfig(SQLModel):
    embedding_model: str = Field(min_length=1)
    graph_build: RagEvalGraphBuildConfig | None = None


def validate_rag_eval_retrieval_config(
    retrieval_config: RagEvalRetrievalConfig | dict[str, Any], strategy: str
) -> RagEvalRetrievalConfig:
    """
    Validate retrieval-build settings for the selected RAG strategy.
    Args:
        retrieval_config: The retrieval configuration to validate.
        strategy: The RAG strategy being used.
    Returns:
        The validated retrieval configuration.
    Raises:
        ValueError: If the strategy is "graphrag" and graph_build is not
        provided in the retrieval_config.
    """
    config = (
        retrieval_config
        if isinstance(retrieval_config, RagEvalRetrievalConfig)
        else RagEvalRetrievalConfig.model_validate(retrieval_config)
    )
    if strategy == "graphrag" and config.graph_build is None:
        raise ValueError("GraphRAG evaluation retrieval_config requires graph_build")
    return config


class RagEvalPairProfileBase(SQLModel):
    name: str = Field(min_length=3)
    rag_profile_id: int
    chunking_profile_id: int
    retrieval_config: RagEvalRetrievalConfig


class RagEvalPairProfileCreateRequest(RagEvalPairProfileBase):
    pass


class RagEvalPairProfileCreate(RagEvalPairProfileBase):
    created_by_user_id: int


class RagEvalPairProfileUpdateRequest(SQLModel):
    name: str | None = Field(default=None, min_length=3)
    retrieval_config: RagEvalRetrievalConfig | None = None


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
    retrieval_config_snapshot: dict[str, Any] = Field(default_factory=dict)
    answer_generation_model_snapshot: dict[str, Any] = Field(default_factory=dict)
    evaluation_model_snapshot: dict[str, Any] = Field(default_factory=dict)


class RagEvalRunStartRequest(SQLModel):
    k: int = Field(default=4, ge=1)
    answer_llm_provider: str
    answer_llm_model: str
    judge_llm_provider: str
    judge_llm_model: str
    judge_embedding_model: str


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
    retrieval_config_snapshot: dict[str, Any]
    answer_generation_model_snapshot: dict[str, Any]
    evaluation_model_snapshot: dict[str, Any]
    aggregate_hit_rate_at_k: float | None = None
    aggregate_mrr_at_k: float | None = None
    aggregate_ragas_metrics: dict[str, Any]
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RagEvalRunDetailRead(RagEvalRunRead):
    query_results: list[RagEvalQueryResultRead] = Field(default_factory=list)
