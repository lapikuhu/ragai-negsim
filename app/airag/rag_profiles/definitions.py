from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.services.llm_models_service import normalize_rag_llm_components
from app.airag.reranking.reranking import list_available_reranker_names

RagStrategy = Literal["crag", "graphrag"]
RagFieldKind = Literal["int", "enum"]


@dataclass(frozen=True)
class RagProfileFieldDefinition:
    name: str
    kind: RagFieldKind
    label: str
    required: bool
    default: Any
    minimum: int | None = None
    maximum: int | None = None
    help_text: str | None = None
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class RagProfileDefinition:
    strategy: RagStrategy
    label: str
    fields: tuple[RagProfileFieldDefinition, ...]


def _crag_definition() -> RagProfileDefinition:
    """
    Create the CRAG (Corrective RAG) profile definition.
    Returns:
        RagProfileDefinition: The CRAG profile definition.
    """
    return RagProfileDefinition(
        strategy="crag",
        label="Corrective RAG",
        fields=(
            RagProfileFieldDefinition(
                name="top_k",
                kind="int",
                label="Retrieved documents",
                required=True,
                default=4,
                minimum=1,
                maximum=20,
                help_text="How many documents to retrieve before reranking.",
            ),
            RagProfileFieldDefinition(
                name="reranker",
                kind="enum",
                label="Reranker",
                required=True,
                default="cross_encoder",
                help_text="Choose how retrieved documents are reordered before grading.",
                options=tuple(list_available_reranker_names()),
            ),
            RagProfileFieldDefinition(
                name="top_n",
                kind="int",
                label="Reranked documents",
                required=True,
                default=3,
                minimum=1,
                maximum=20,
                help_text="How many documents to keep after reranking.",
            ),
            RagProfileFieldDefinition(
                name="max_rewrite_attempts",
                kind="int",
                label="Rewrite attempts",
                required=True,
                default=2,
                minimum=0,
                maximum=10,
                help_text="How many query rewrites CRAG may try before falling back.",
            ),
        ),
    )


def _graphrag_definition() -> RagProfileDefinition:
    """
    Create the GraphRAG (Knowledge Graph RAG) profile definition.
    Returns:
        RagProfileDefinition: The GraphRAG profile definition.
    """
    return RagProfileDefinition(
        strategy="graphrag",
        label="Knowledge Graph RAG",
        fields=(
            RagProfileFieldDefinition(
                name="retrieval_mode",
                kind="enum",
                label="Retrieval mode",
                required=True,
                default="semantic",
                help_text="Use semantic graph context, text-to-Cypher, or both.",
                options=("semantic", "cypher", "hybrid"),
            ),
            RagProfileFieldDefinition(
                name="evidence_limit",
                kind="int",
                label="Evidence chunks",
                required=True,
                default=6,
                minimum=1,
                maximum=30,
            ),
            RagProfileFieldDefinition(
                name="traversal_depth",
                kind="int",
                label="Traversal depth",
                required=True,
                default=2,
                minimum=1,
                maximum=5,
            ),
            RagProfileFieldDefinition(
                name="rrf_k",
                kind="int",
                label="Hybrid RRF constant",
                required=True,
                default=60,
                minimum=1,
                maximum=200,
            ),
        ),
    )


def list_rag_profile_definitions() -> list[RagProfileDefinition]:
    """
    List all available RAG profile definitions.
    Returns:
        list[RagProfileDefinition]: A list of RAG profile definitions.
    """
    return [_crag_definition(), _graphrag_definition()]


def get_rag_profile_definition(strategy: str) -> RagProfileDefinition:
    """
    Get the RAG profile definition for a given strategy.
    Args:
        strategy (str): The RAG strategy name.
    Returns:
        RagProfileDefinition: The RAG profile definition.
    Raises:
        ValueError: If the strategy is not supported.
    """
    normalized = strategy.strip().lower()
    if normalized == "crag":
        return _crag_definition()
    if normalized == "graphrag":
        return _graphrag_definition()
    raise ValueError(f"Unsupported RAG strategy: {strategy}")


def normalize_rag_profile_config(
    strategy: str,
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Normalize and validate a RAG profile configuration.
    Args:
        strategy (str): The RAG strategy name.
        config (dict[str, Any] | None): The RAG profile configuration.
    Returns:
        dict[str, Any]: The normalized RAG profile configuration.
    Raises:
        ValueError: If the configuration is invalid or contains unknown 
        fields.
    """
    definition = get_rag_profile_definition(strategy)
    if config is None:
        config = {}
    elif not isinstance(config, dict):
        raise ValueError("RAG profile config must be a dictionary or None")

    allowed_names = {field.name for field in definition.fields} | {"llm_components"}
    unknown = sorted(set(config) - allowed_names)
    if unknown:
        raise ValueError(
            f"Unknown config fields for {strategy}: {', '.join(unknown)}"
        )

    normalized: dict[str, Any] = {}
    for field in definition.fields:
        value = config.get(field.name, field.default)
        if field.kind == "int":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{field.name} must be an integer")
            if field.minimum is not None and value < field.minimum:
                raise ValueError(f"{field.name} must be >= {field.minimum}")
            if field.maximum is not None and value > field.maximum:
                raise ValueError(f"{field.name} must be <= {field.maximum}")
        elif field.kind == "enum":
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field.name} must be a non-empty string")
            if value not in field.options:
                raise ValueError(
                    f"{field.name} must be one of: {', '.join(field.options)}"
                )
        normalized[field.name] = value

    if definition.strategy == "crag":
        if normalized["top_n"] > normalized["top_k"]:
            raise ValueError("top_n must be <= top_k")

        if normalized["reranker"] == "none":
            normalized["top_n"] = normalized["top_k"]

    normalized["llm_components"] = normalize_rag_llm_components(
        config.get("llm_components")
    )

    return normalized
