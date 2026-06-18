from datetime import datetime
from typing import Any

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.airag.embeddings.embeddings import get_embedding_model_info
from app.services.llm_models_service import (
    get_default_openai_chat_model,
    normalize_llm_selection,
)

# Consider moving to config
GRAPH_EXTRACTORS = {"simple", "implicit", "schema"}
GRAPH_PROVIDERS = {"openai", "ollama"}
SEMANTIC_GRAPH_EXTRACTORS = {"simple", "schema"}


def _normalize_graph_extractors(
    extractors: list[str],
    *,
    require_supported_combination: bool,
) -> list[str]:
    if not extractors:
        raise ValueError("Knowledge graph requires at least one extractor")
    if len(extractors) != len(set(extractors)):
        raise ValueError("Knowledge graph extractors contain duplicate values")

    unsupported = sorted(set(extractors) - GRAPH_EXTRACTORS)
    if unsupported:
        raise ValueError(
            f"Unsupported knowledge graph extractors: {', '.join(unsupported)}"
        )

    if require_supported_combination:
        semantic_extractors = [
            extractor
            for extractor in extractors
            if extractor in SEMANTIC_GRAPH_EXTRACTORS
        ]
        if len(semantic_extractors) != 1:
            raise ValueError(
                "Knowledge graph requires exactly one semantic extractor: "
                "`schema` or `simple`"
            )

    return extractors


def normalize_knowledge_graph_build_config(
    config: dict[str, Any] | None,
    *,
    require_supported_combination: bool = False,
) -> dict[str, Any]:
    values = dict(config or {})
    if require_supported_combination:
        llm_selection = normalize_llm_selection(
            values.get("llm_provider"),
            values.get("llm_model"),
        )
        llm_provider = llm_selection["provider"]
        llm_model = llm_selection["model"]
    else:
        llm_provider = str(values.get("llm_provider", "openai")).strip().lower()
        if llm_provider not in GRAPH_PROVIDERS:
            raise ValueError(f"Unsupported LLM provider: {llm_provider}")
        llm_model = str(
            values.get(
                "llm_model",
                get_default_openai_chat_model()
                if llm_provider == "openai"
                else "llama3.1",
            )
        ).strip()

    extractors = _normalize_graph_extractors(
        list(values.get("extractors", ["schema"])),
        require_supported_combination=require_supported_combination,
    )

    embedding_model = str(
        values.get("embedding_model", "text-embedding-3-small")
    ).strip()
    if require_supported_combination:
        embedding_model_info = get_embedding_model_info(embedding_model)
        embedding_provider = embedding_model_info["provider"]
    else:
        try:
            embedding_model_info = get_embedding_model_info(embedding_model)
            embedding_provider = embedding_model_info["provider"]
        except ValueError:
            embedding_provider = str(
                values.get("embedding_provider", "openai")
            ).strip().lower()
            if embedding_provider not in GRAPH_PROVIDERS:
                raise ValueError(
                    f"Unsupported embedding provider: {embedding_provider}"
                )

    normalized = {
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "extractors": extractors,
        "strict_schema": bool(values.get("strict_schema", True)),
        "max_paths_per_chunk": int(values.get("max_paths_per_chunk", 10)),
        "ollama_base_url": values.get("ollama_base_url", "http://localhost:11434"),
    }
    if not str(normalized["llm_model"]).strip():
        raise ValueError("LLM model must not be blank")
    if not str(normalized["embedding_model"]).strip():
        raise ValueError("Embedding model must not be blank")
    if normalized["max_paths_per_chunk"] < 1:
        raise ValueError("max_paths_per_chunk must be at least 1")
    return normalized


class KnowledgeGraphIndexBase(SQLModel):
    name: str = Field(min_length=3)
    corpus_index_id: int
    build_config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("build_config")
    @classmethod
    def validate_build_config(cls, value: dict[str, Any]) -> dict[str, Any]:
        return normalize_knowledge_graph_build_config(value)


class KnowledgeGraphIndexCreate(KnowledgeGraphIndexBase):
    @field_validator("build_config")
    @classmethod
    def validate_build_config_for_create(
        cls,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        return normalize_knowledge_graph_build_config(
            value,
            require_supported_combination=True,
        )


class KnowledgeGraphIndexUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=3)
    build_config: dict[str, Any] | None = None

    @field_validator("build_config")
    @classmethod
    def validate_build_config(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        return normalize_knowledge_graph_build_config(
            value,
            require_supported_combination=True,
        )


class KnowledgeGraphIndexRead(KnowledgeGraphIndexBase):
    id: int
    status: str
    active_generation: str | None = None
    latest_build_error: str | None = None
    locked_at: datetime | None = None
    built_at: datetime | None = None
    created_at: datetime
    last_updated: datetime


class KnowledgeGraphIndexReadWithUsage(KnowledgeGraphIndexRead):
    rag_profile_ids: list[int] = Field(default_factory=list)
    simulation_ids: list[int] = Field(default_factory=list)
    active_job_id: int | None = None
