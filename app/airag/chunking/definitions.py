from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ChunkingStrategy = Literal["recursive", "semantic", "hybrid"]

# 
@dataclass(frozen=True)
class ChunkerFieldDefinition:
    name: str
    kind: Literal["int", "string", "string_list"]
    label: str
    required: bool
    default: Any
    minimum: int | None = None
    maximum: int | None = None
    help_text: str | None = None


@dataclass(frozen=True)
class ChunkerDefinition:
    strategy: ChunkingStrategy
    label: str
    supports_ingestion: bool
    fields: tuple[ChunkerFieldDefinition, ...]


_DEFAULT_SEPARATORS = ("\n\n", "\n", " ", "")
# Definitions for supported chunking strategies and their configuration 
# fields, along with normalization and validation logic.
_DEFINITIONS: dict[ChunkingStrategy, ChunkerDefinition] = {
    "recursive": ChunkerDefinition(
        strategy="recursive",
        label="Recursive character splitter",
        supports_ingestion=True,
        fields=(
            ChunkerFieldDefinition(
                "chunk_size",
                "int",
                "Chunk size",
                True,
                1000,
                minimum=100,
                maximum=8000,
            ),
            ChunkerFieldDefinition(
                "chunk_overlap",
                "int",
                "Chunk overlap",
                True,
                200,
                minimum=0,
                maximum=2000,
            ),
            ChunkerFieldDefinition(
                "separators",
                "string_list",
                "Separators",
                False,
                _DEFAULT_SEPARATORS,
            ),
        ),
    ),
    "semantic": ChunkerDefinition(
        strategy="semantic",
        label="Semantic chunker",
        supports_ingestion=False,
        fields=(
            ChunkerFieldDefinition(
                "breakpoint_threshold_type",
                "string",
                "Breakpoint threshold type",
                True,
                "percentile",
            ),
            ChunkerFieldDefinition(
                "breakpoint_threshold_amount",
                "int",
                "Breakpoint threshold amount",
                True,
                90,
                minimum=1,
            ),
            ChunkerFieldDefinition(
                "buffer_size",
                "int",
                "Buffer size",
                True,
                1,
                minimum=0,
            ),
        ),
    ),
    "hybrid": ChunkerDefinition(
        strategy="hybrid",
        label="Hybrid semantic + recursive splitter",
        supports_ingestion=False,
        fields=(
            ChunkerFieldDefinition(
                "breakpoint_threshold_type",
                "string",
                "Breakpoint threshold type",
                True,
                "percentile",
            ),
            ChunkerFieldDefinition(
                "breakpoint_threshold_amount",
                "int",
                "Breakpoint threshold amount",
                True,
                90,
                minimum=1,
            ),
            ChunkerFieldDefinition(
                "buffer_size",
                "int",
                "Buffer size",
                True,
                1,
                minimum=0,
            ),
            ChunkerFieldDefinition(
                "chunk_size",
                "int",
                "Chunk size",
                True,
                1000,
                minimum=100,
                maximum=8000,
            ),
            ChunkerFieldDefinition(
                "chunk_overlap",
                "int",
                "Chunk overlap",
                True,
                200,
                minimum=0,
                maximum=2000,
            ),
            ChunkerFieldDefinition(
                "separators",
                "string_list",
                "Separators",
                False,
                _DEFAULT_SEPARATORS,
            ),
        ),
    ),
}


def list_chunker_definitions() -> list[ChunkerDefinition]:
    """
    List all available chunker definitions.
    Args:
        None
    Returns:
        List of chunker definitions.
    """
    return list(_DEFINITIONS.values())


def get_chunker_definition(strategy: str) -> ChunkerDefinition:
    """
    Get the chunker definition for a given strategy.
    Args:
        strategy: The chunking strategy.
    Returns:
        The chunker definition.
    """
    try:
        return _DEFINITIONS[strategy]  # type: ignore[index]
    except KeyError as exc:
        raise ValueError(f"Unsupported chunking strategy: {strategy}") from exc


def normalize_chunking_profile_config(
    strategy: str,
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Normalize and validate the chunking profile config for a given strategy.
    Args:
        strategy: The chunking strategy.
        config: The chunking profile config.
    Returns:
        The normalized chunking profile config.
    """
    definition = get_chunker_definition(strategy)
    if config is None:
        config = {}
    elif not isinstance(config, dict):
        raise ValueError("Config must be a dictionary or None")
    allowed_names = {field.name for field in definition.fields}
    unknown = sorted(set(config) - allowed_names)
    if unknown:
        raise ValueError(
            f"Unknown config fields for {strategy}: {', '.join(unknown)}"
        )

    normalized: dict[str, Any] = {}
    for field in definition.fields:
        value = config.get(field.name, field.default)
        if field.kind == "string_list" and field.name not in config:
            value = list(value)
        if field.kind == "int":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{field.name} must be an integer")
            if field.minimum is not None and value < field.minimum:
                raise ValueError(f"{field.name} must be >= {field.minimum}")
            if field.maximum is not None and value > field.maximum:
                raise ValueError(f"{field.name} must be <= {field.maximum}")
        elif field.kind == "string":
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field.name} must be a non-empty string")
        elif field.kind == "string_list":
            if not isinstance(value, list) or any(
                not isinstance(item, str) for item in value
            ):
                raise ValueError(f"{field.name} must be a list of strings")
        normalized[field.name] = value

    return normalized
