from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field as PydanticField, field_validator, model_validator
from sqlmodel import Field, SQLModel

from app.airag.embeddings.embeddings import get_embedding_model_info
from app.airag.reranking.reranking import is_reranker_available
from app.services.llm_models_service import normalize_llm_selection


StrictPositiveInt = Annotated[int, PydanticField(strict=True, ge=1)]


class _StrictSchema(SQLModel):
    model_config = ConfigDict(extra="forbid")


class LLMSelection(_StrictSchema):
    provider: str = PydanticField(min_length=1)
    model: str = PydanticField(min_length=1)

    @field_validator("provider", "model")
    @classmethod
    def require_non_empty_selection_value(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("LLM provider and model must be non-empty")
        return normalized

    @model_validator(mode="after")
    def normalize_and_validate_selection(self) -> "LLMSelection":
        selection = normalize_llm_selection(self.provider, self.model)
        self.provider = selection["provider"]
        self.model = selection["model"]
        return self


class RecursiveChunkingConfiguration(_StrictSchema):
    strategy: Literal["recursive"] = "recursive"
    chunk_size: Annotated[int, PydanticField(strict=True, ge=100, le=8000)] = 1000
    chunk_overlap: Annotated[int, PydanticField(strict=True, ge=0, le=2000)] = 200
    separators: list[str] = PydanticField(
        default_factory=lambda: ["\n\n", "\n", " ", ""]
    )

    @model_validator(mode="after")
    def validate_overlap(self) -> "RecursiveChunkingConfiguration":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class SemanticChunkingConfiguration(_StrictSchema):
    strategy: Literal["semantic"] = "semantic"
    breakpoint_threshold_type: str = PydanticField(
        default="percentile",
        min_length=1,
    )
    breakpoint_threshold_amount: Annotated[int, PydanticField(strict=True, ge=1)] = 90
    buffer_size: Annotated[int, PydanticField(strict=True, ge=0)] = 1

    @field_validator("breakpoint_threshold_type")
    @classmethod
    def normalize_breakpoint_threshold_type(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("breakpoint_threshold_type must be a non-empty string")
        return normalized


class HybridChunkingConfiguration(SemanticChunkingConfiguration):
    strategy: Literal["hybrid"] = "hybrid"
    chunk_size: Annotated[int, PydanticField(strict=True, ge=100, le=8000)] = 1000
    chunk_overlap: Annotated[int, PydanticField(strict=True, ge=0, le=2000)] = 200
    separators: list[str] = PydanticField(
        default_factory=lambda: ["\n\n", "\n", " ", ""]
    )

    @model_validator(mode="after")
    def validate_overlap(self) -> "HybridChunkingConfiguration":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


ChunkingEvaluationConfiguration = Annotated[
    RecursiveChunkingConfiguration
    | SemanticChunkingConfiguration
    | HybridChunkingConfiguration,
    PydanticField(discriminator="strategy"),
]


class _ResponseLLMSelections(_StrictSchema):
    document_grader: LLMSelection
    query_rewriter: LLMSelection
    answer_generator: LLMSelection
    hallucination_grader: LLMSelection
    answer_grader: LLMSelection
    fallback_generator: LLMSelection


class CragEvaluationConfiguration(_ResponseLLMSelections):
    strategy: Literal["crag"] = "crag"
    retrieval_embedding_model: str = PydanticField(
        default="text-embedding-3-small",
        min_length=1,
    )
    top_k: Annotated[int, PydanticField(strict=True, ge=1, le=20)] = 4
    reranker: str = PydanticField(default="cross_encoder", min_length=1)
    top_n: Annotated[int, PydanticField(strict=True, ge=1, le=20)] = 3
    rewrite_limit: Annotated[int, PydanticField(strict=True, ge=0, le=10)] = 2

    @field_validator("retrieval_embedding_model")
    @classmethod
    def validate_retrieval_embedding_model(cls, value: str) -> str:
        normalized = value.strip()
        get_embedding_model_info(normalized)
        return normalized

    @field_validator("reranker")
    @classmethod
    def validate_reranker(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not is_reranker_available(normalized):
            raise ValueError(f"Unavailable reranker: {normalized}")
        return normalized

    @model_validator(mode="after")
    def validate_reranking_capacity(self) -> "CragEvaluationConfiguration":
        if self.top_n > self.top_k:
            raise ValueError("top_n must be less than or equal to top_k")
        if self.reranker == "none":
            self.top_n = self.top_k
        return self


class GraphRagEvaluationConfiguration(_ResponseLLMSelections):
    strategy: Literal["graphrag"] = "graphrag"
    extraction_llm: LLMSelection
    graph_embedding_model: str = PydanticField(
        default="text-embedding-3-small",
        min_length=1,
    )
    max_paths_per_chunk: Annotated[
        int, PydanticField(strict=True, ge=1, le=100)
    ] = 10
    retrieval_mode: Literal["semantic", "cypher", "hybrid"] = "semantic"
    evidence_limit: Annotated[int, PydanticField(strict=True, ge=1, le=30)] = 6
    traversal_depth: Annotated[int, PydanticField(strict=True, ge=1, le=5)] = 2
    rrf_constant: Annotated[int, PydanticField(strict=True, ge=1, le=200)] = 60

    @field_validator("graph_embedding_model")
    @classmethod
    def validate_graph_embedding_model(cls, value: str) -> str:
        normalized = value.strip()
        get_embedding_model_info(normalized)
        return normalized


RagEvaluationConfiguration = Annotated[
    CragEvaluationConfiguration | GraphRagEvaluationConfiguration,
    PydanticField(discriminator="strategy"),
]


class RagEvalMetricsConfiguration(_StrictSchema):
    k: StrictPositiveInt = 4
    ragas_judge: LLMSelection
    judge_embedding_model: str = PydanticField(
        default="text-embedding-3-small",
        min_length=1,
    )

    @field_validator("judge_embedding_model")
    @classmethod
    def validate_judge_embedding_model(cls, value: str) -> str:
        normalized = value.strip()
        get_embedding_model_info(normalized)
        return normalized


class RagEvalConfigurationBase(_StrictSchema):
    name: str = PydanticField(min_length=3)
    chunking: ChunkingEvaluationConfiguration
    rag: RagEvaluationConfiguration
    metrics: RagEvalMetricsConfiguration

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("name must contain at least 3 non-whitespace characters")
        return normalized

    @model_validator(mode="after")
    def validate_metric_context_capacity(self) -> "RagEvalConfigurationBase":
        if isinstance(self.rag, CragEvaluationConfiguration):
            capacity = self.rag.top_n
            capacity_field = "rag.top_n"
        else:
            capacity = self.rag.evidence_limit
            capacity_field = "rag.evidence_limit"
        if self.metrics.k > capacity:
            raise ValueError(
                f"metrics.k must be less than or equal to {capacity_field}"
            )
        return self


class RagEvalConfigurationCreateRequest(RagEvalConfigurationBase):
    pass


class RagEvalConfigurationCreate(RagEvalConfigurationBase):
    created_by_user_id: int


class RagEvalConfigurationUpdateRequest(_StrictSchema):
    name: str | None = PydanticField(default=None, min_length=3)
    chunking: ChunkingEvaluationConfiguration | None = None
    rag: RagEvaluationConfiguration | None = None
    metrics: RagEvalMetricsConfiguration | None = None

    @model_validator(mode="after")
    def require_patch_field(self) -> "RagEvalConfigurationUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Configuration patch must include at least one field")
        return self


class RagEvalConfigurationUpdate(RagEvalConfigurationUpdateRequest):
    last_edit_by_user_id: int | None = None


class RagEvalConfigurationRead(RagEvalConfigurationBase):
    id: int
    created_by_user_id: int
    last_edit_by_user_id: int | None = None
    created_at: datetime
    last_updated: datetime


def apply_rag_eval_configuration_patch(
    current: RagEvalConfigurationBase | dict[str, Any],
    patch: RagEvalConfigurationUpdateRequest | dict[str, Any],
) -> RagEvalConfigurationCreateRequest:
    """Apply a top-level replacement patch and fully revalidate the result."""
    current_config = RagEvalConfigurationCreateRequest.model_validate(current)
    validated_patch = (
        patch
        if isinstance(patch, RagEvalConfigurationUpdateRequest)
        else RagEvalConfigurationUpdateRequest.model_validate(patch)
    )
    values = current_config.model_dump(mode="python")
    values.update(
        validated_patch.model_dump(
            include={"name", "chunking", "rag", "metrics"},
            exclude_unset=True,
            mode="python",
        )
    )
    return RagEvalConfigurationCreateRequest.model_validate(values)


def dump_rag_eval_configuration_snapshot(
    configuration: RagEvalConfigurationBase | dict[str, Any],
) -> dict[str, Any]:
    """Return a canonical JSON-compatible user-authored configuration snapshot."""
    normalized = RagEvalConfigurationCreateRequest.model_validate(configuration)
    return normalized.model_dump(mode="json")


# Legacy run/result transport schemas are retained until their persistence and API
# replacements land. Configuration CRUD uses only the typed schemas above.


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
