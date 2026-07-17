from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field as PydanticField,
    field_validator,
    model_validator,
)
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
    k: StrictPositiveInt = 3
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
    raw_configuration = (
        configuration.model_dump(
            include={"name", "chunking", "rag", "metrics"},
            mode="python",
        )
        if isinstance(configuration, RagEvalConfigurationBase)
        else configuration
    )
    normalized = RagEvalConfigurationCreateRequest.model_validate(raw_configuration)
    return normalized.model_dump(mode="json")


class RagEvalFinalChunkMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    chunk_index: int | None = PydanticField(default=None, ge=0)
    source: str | None = None
    score: float | None = None
    rerank_score: float | None = None
    retrieval_strategy: str | None = None
    retrieval_mode: str | None = None
    evidence_path: str | None = None


class RagEvalFinalChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: StrictPositiveInt
    content: str = PydanticField(min_length=1)
    metadata: RagEvalFinalChunkMetadata = PydanticField(
        default_factory=RagEvalFinalChunkMetadata
    )


class RagEvalQueryResultCreate(_StrictSchema):
    example_id: str = PydanticField(min_length=1)
    category: str = PydanticField(min_length=1)
    answerable: bool
    query: str = PydanticField(min_length=1)
    reference_answer: str | None = None
    actual_answer: str = PydanticField(min_length=1)
    final_chunks: list[RagEvalFinalChunk] = PydanticField(default_factory=list)
    first_relevant_rank: StrictPositiveInt | None = None
    hit_at_k: bool | None = None
    mrr_at_k: Annotated[float, PydanticField(ge=0.0, le=1.0)] | None = None
    successful_abstention: bool | None = None
    false_positive_context: bool | None = None
    faithfulness: Annotated[float, PydanticField(ge=0.0, le=1.0)] | None = None
    answer_relevancy: Annotated[float, PydanticField(ge=0.0, le=1.0)] | None = None
    context_precision: Annotated[float, PydanticField(ge=0.0, le=1.0)] | None = None
    context_recall: Annotated[float, PydanticField(ge=0.0, le=1.0)] | None = None
    answer_correctness: Annotated[float, PydanticField(ge=0.0, le=1.0)] | None = None

    @field_validator("final_chunks")
    @classmethod
    def validate_final_chunk_ranks(
        cls,
        value: list[RagEvalFinalChunk],
    ) -> list[RagEvalFinalChunk]:
        ranks = [chunk.rank for chunk in value]
        if ranks != list(range(1, len(value) + 1)):
            raise ValueError(
                "final_chunks must have ordered consecutive ranks starting at 1"
            )
        return value

    @model_validator(mode="after")
    def validate_answerability_metrics(self) -> "RagEvalQueryResultCreate":
        if self.answerable:
            if (
                self.successful_abstention is not None
                or self.false_positive_context is not None
            ):
                raise ValueError(
                    "Answerable rows cannot contain unanswerable-only metrics"
                )
        elif (
            self.first_relevant_rank is not None
            or self.hit_at_k is not None
            or self.mrr_at_k is not None
        ):
            raise ValueError("Unanswerable rows cannot contain retrieval rank metrics")
        return self


class RagEvalQueryResultRead(RagEvalQueryResultCreate):
    id: int
    run_id: int


class RagEvalRunRead(_StrictSchema):
    id: int
    configuration_id: int
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    stage: Literal[
        "queued",
        "preparing",
        "chunking",
        "building_index",
        "building_graph",
        "evaluating",
        "scoring",
        "cleaning_up",
        "persisting",
        "finished",
        "cleanup_pending",
    ]
    progress: Annotated[float, PydanticField(ge=0.0, le=100.0)]
    completed_examples: Annotated[int, PydanticField(ge=0)]
    total_examples: Annotated[int, PydanticField(ge=0)]
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancel_requested: bool
    cancellation_requested_at: datetime | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    configuration_snapshot: dict[str, Any]
    suite_version: str
    suite_content_hash: str
    resolved_pipeline_snapshot: dict[str, Any]
    overall_metrics: dict[str, Any]
    category_metrics: dict[str, Any]


class RagEvalRunDetailRead(RagEvalRunRead):
    query_results: list[RagEvalQueryResultRead] = PydanticField(default_factory=list)


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
    config = RagEvalRetrievalConfig.model_validate(retrieval_config)
    if strategy == "graphrag" and config.graph_build is None:
        raise ValueError("GraphRAG evaluation retrieval_config requires graph_build")
    return config


# Temporary transport declarations keep the legacy route/service importable while
# those layers are replaced in a later task. Target persistence APIs above use only
# complete RagEvalConfiguration payloads.
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
    """Legacy service import shim; target enqueues use a configuration instance."""

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
