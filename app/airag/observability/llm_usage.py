from __future__ import annotations

from typing import Any, Iterable

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.runnables.config import RunnableConfig, ensure_config, merge_configs


def _ordered_unique(values: Iterable[str]) -> list[str]:
    """
    Return a list of unique values in the order they were first encountered.
    Args:
        values: An iterable of values.
    Returns:
        A list of unique values in the order they were first encountered.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def extend_runnable_config(
    config: RunnableConfig | None = None,
    *,
    tags: Iterable[str] | None = None,
    metadata: dict[str, Any] | None = None,
    callbacks: list[Any] | None = None,
    run_name: str | None = None,
) -> RunnableConfig:
    """
    Extend a runnable configuration with additional parameters.
    Args:
        config: The base runnable configuration.
        tags: Optional tags to add to the configuration.
        metadata: Optional metadata to add to the configuration.
        callbacks: Optional callbacks to add to the configuration.
        run_name: Optional run name to add to the configuration.
    Returns:
        The extended runnable configuration.
    """
    base_config = ensure_config(config)
    base_tags = [str(tag) for tag in base_config.get("tags", [])]
    overlay: RunnableConfig = {}
    if tags:
        overlay["tags"] = list(tags)
    if metadata:
        overlay["metadata"] = dict(metadata)
    if callbacks is not None:
        overlay["callbacks"] = list(callbacks)
    if run_name:
        overlay["run_name"] = run_name

    merged = merge_configs(base_config, overlay)
    merged["tags"] = _ordered_unique(
        [*base_tags, *(str(tag) for tag in (overlay.get("tags") or []))]
    )
    return merged


def create_usage_tracking_context(
    *,
    tags: Iterable[str] | None = None,
    metadata: dict[str, Any] | None = None,
    run_name: str | None = None,
) -> tuple[UsageMetadataCallbackHandler, RunnableConfig]:
    """
    Create a usage tracking context with a callback handler and runnable 
    configuration.
    Args:
        tags: Optional tags to add to the configuration.
        metadata: Optional metadata to add to the configuration.
        run_name: Optional run name to add to the configuration.
    Returns:
        A tuple containing the usage metadata callback handler and the 
        runnable configuration.
    """
    handler = UsageMetadataCallbackHandler()
    config = extend_runnable_config(
        callbacks=[handler],
        tags=tags,
        metadata=metadata,
        run_name=run_name,
    )
    return handler, config


def bind_runnable_config(
    runnable: Any,
    config: RunnableConfig | None = None,
    *,
    tags: Iterable[str] | None = None,
    metadata: dict[str, Any] | None = None,
    run_name: str | None = None,
) -> Any:
    """
    Bind a runnable configuration to a runnable.
    Args:
        runnable: The runnable to bind the configuration to.
        config: The base runnable configuration.
        tags: Optional tags to add to the configuration.
        metadata: Optional metadata to add to the configuration.
        run_name: Optional run name to add to the configuration.
    Returns:
        The runnable with the bound configuration.
    """
    bound_config = extend_runnable_config(
        config,
        tags=tags,
        metadata=metadata,
        run_name=run_name,
    )
    if hasattr(runnable, "with_config"):
        return runnable.with_config(bound_config)
    return runnable


def invoke_with_config(
    runnable: Any,
    payload: Any,
    config: RunnableConfig | None = None,
) -> Any:
    """
    Invoke the runnable with the given payload and configuration.
    Args:
        runnable: The runnable to invoke.
        payload: The input payload for the runnable.
        config: Optional runnable configuration.
    Returns:
        The result of invoking the runnable.
    """
    if config is None:
        return runnable.invoke(payload)
    try:
        return runnable.invoke(payload, config=config)
    except TypeError as exc:
        if "config" not in str(exc):
            raise
        return runnable.invoke(payload)


def summarize_usage_handler(handler: UsageMetadataCallbackHandler) -> dict[str, Any]:
    """
    Summarize the usage metadata from a usage metadata callback handler.
    Args:
        handler: The usage metadata callback handler.
    Returns:
        A dictionary containing the summarized usage metadata.
    """
    raw_models = {
        str(model_name): dict(usage)
        for model_name, usage in handler.usage_metadata.items()
    }
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    for usage in raw_models.values():
        totals["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
        totals["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
        totals["total_tokens"] += int(usage.get("total_tokens", 0) or 0)

    return {
        "totals": totals,
        "models": raw_models,
    }
