from __future__ import annotations

from dataclasses import dataclass

from app.airag.chunking import get_chunker_definition, normalize_chunking_profile_config


@dataclass(frozen=True)
class ResolvedChunkingOptions:
    chunker: str
    chunk_size: int = 1000
    chunk_overlap: int = 200
    separators: list[str] | None = None
    breakpoint_threshold_type: str = "percentile"
    breakpoint_threshold_amount: int = 90
    buffer_size: int = 1
    preview: bool = False


@dataclass(frozen=True)
class ResolvedIngestionOptions:
    header_depth: int
    dynamic_header_depth: bool
    chunker: str
    chunk_size: int = 1000
    chunk_overlap: int = 200
    separators: list[str] | None = None
    breakpoint_threshold_type: str = "percentile"
    breakpoint_threshold_amount: int = 90
    buffer_size: int = 1


def resolve_chunking_profile_options(profile, preview: bool) -> ResolvedChunkingOptions:
    """
    Resolve the chunking profile options.
    Args:
        profile: The chunking profile to resolve.
        preview: Whether to enable preview mode.
    Returns:
        The resolved chunking options.
    """
    config = normalize_chunking_profile_config(profile.strategy, profile.config)
    return ResolvedChunkingOptions(chunker=profile.strategy, preview=preview, **config)


def resolve_ingestion_profile_options(profile, header_depth: int, dynamic_header_depth: bool) -> ResolvedIngestionOptions:
    """
    Resolve the ingestion profile options.
    Args:
        profile: The ingestion profile to resolve.
        header_depth: The header depth for the ingestion.
        dynamic_header_depth: Whether to enable dynamic header depth.
    Returns:
        The resolved ingestion options.
    """
    definition = get_chunker_definition(profile.strategy)
    if not definition.supports_ingestion:
        raise ValueError(f"Chunking strategy '{profile.strategy}' does not support ingestion")
    config = normalize_chunking_profile_config(profile.strategy, profile.config)
    return ResolvedIngestionOptions(
        header_depth=header_depth,
        dynamic_header_depth=dynamic_header_depth,
        chunker=profile.strategy,
        **config,
    )
