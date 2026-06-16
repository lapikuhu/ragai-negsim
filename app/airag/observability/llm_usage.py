from __future__ import annotations

import threading
from typing import Any, Iterable

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from langchain_core.runnables.config import RunnableConfig, ensure_config, merge_configs

#TODO: Move to to config file
PUBLIC_AGENT_NAMES = ("coach", "counterpart", "user_proxy", "evaluator")


class AgentTokenUsageCallbackHandler(BaseCallbackHandler):
    """Track total token usage by agent across a runnable tree."""

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._run_agents: dict[Any, str] = {}
        self.agent_total_tokens: dict[str, int] = {}

    def _resolve_agent(
        self,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Resolve the agent name from the provided tags and metadata. The 
        agent name is determined by checking the metadata for an "agent" 
        key or by looking for tags that start with "agent:". If a valid 
        agent name is found in either source, it is returned; otherwise, 
        None is returned.
        Args:
            tags: Optional list of tags to check for an agent name.
            metadata: Optional dictionary of metadata to check for an 
                agent name.
        Returns:
            The resolved agent name if found, otherwise None.
        """
        metadata_agent = metadata.get("agent") if isinstance(metadata, dict) else None
        if isinstance(metadata_agent, str) and metadata_agent in PUBLIC_AGENT_NAMES:
            return metadata_agent

        for tag in tags or []:
            if not isinstance(tag, str) or not tag.startswith("agent:"):
                continue
            agent_name = tag.split(":", 1)[1]
            if agent_name in PUBLIC_AGENT_NAMES:
                return agent_name
        return None

    def _remember_agent(self, run_id: Any, **kwargs: Any) -> None:
        """
        Remember the agent associated with a specific run ID. This method 
        resolves the agent name from the provided tags and metadata, and 
        if a valid agent name is found, it stores it in the internal 
        mapping of run IDs to agent names.
        Args:
            run_id: The unique identifier for the current run.
            **kwargs: Additional keyword arguments that may contain tags 
                and metadata for resolving the agent name.
        Returns:
            None
        """
        agent_name = self._resolve_agent(
            tags=kwargs.get("tags"),
            metadata=kwargs.get("metadata"),
        )
        if agent_name is None:
            return
        with self._lock:
            self._run_agents[run_id] = agent_name

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Remember the agent associated with a specific run ID when a chat
        model starts. This method is called when a chat model is initiated,
        and it resolves the agent name from the provided tags and metadata.
        Args:
            serialized: The serialized representation of the chat model.
            messages: The list of messages associated with the chat model.
            run_id: The unique identifier for the current run.
            **kwargs: Additional keyword arguments that may contain tags
                and metadata for resolving the agent name.
        Returns:
            None
        """
        self._remember_agent(run_id, **kwargs)

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> Any:
        self._remember_agent(run_id, **kwargs)

    def on_llm_end(self, response: LLMResult, *, run_id: Any, **kwargs: Any) -> Any:
        """
        Handle the end of an LLM run by extracting usage metadata and
        updating the total token usage for the associated agent. This method
        is called when an LLM run completes, and it retrieves the usage
        metadata from the response, resolves the agent name, and updates
        the total token count for that agent.
        Args:
            response: The LLMResult object containing the response from 
                the LLM run.
            run_id: The unique identifier for the current run.
            **kwargs: Additional keyword arguments that may contain tags
                and metadata for resolving the agent name.
        Returns:
            None
        """
        usage_metadata = None
        try:
            generation = response.generations[0][0]
        except IndexError:
            generation = None

        if isinstance(generation, ChatGeneration):
            message = generation.message
            if isinstance(message, AIMessage):
                usage_metadata = message.usage_metadata

        if usage_metadata is None:
            return

        with self._lock:
            agent_name = self._run_agents.pop(
                run_id,
                self._resolve_agent(
                    tags=kwargs.get("tags"),
                    metadata=kwargs.get("metadata"),
                ),
            )
            if agent_name is None:
                return
            total_tokens = int(usage_metadata.get("total_tokens", 0) or 0)
            self.agent_total_tokens[agent_name] = (
                self.agent_total_tokens.get(agent_name, 0) + total_tokens
            )

    def on_llm_error(self, error: BaseException, *, run_id: Any, **kwargs: Any) -> Any:
        """
        Handle an error that occurs during an LLM run by removing the associated
        agent from the tracking dictionary. This method is called when an LLM
        run encounters an error.
        Args:
            error: The exception that occurred during the LLM run.
            run_id: The unique identifier for the current run.
            **kwargs: Additional keyword arguments that may contain tags
                and metadata for resolving the agent name.
        Returns:
            None
        """
        with self._lock:
            self._run_agents.pop(run_id, None)


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
) -> tuple[
    UsageMetadataCallbackHandler,
    AgentTokenUsageCallbackHandler,
    RunnableConfig,
]:
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
    public_handler = AgentTokenUsageCallbackHandler()
    config = extend_runnable_config(
        callbacks=[handler, public_handler],
        tags=tags,
        metadata=metadata,
        run_name=run_name,
    )
    return handler, public_handler, config


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


def summarize_agent_token_usage_handler(
    handler: AgentTokenUsageCallbackHandler,
) -> dict[str, int]:
    """Return public-safe total token counts by agent."""
    return {
        agent_name: int(total_tokens)
        for agent_name, total_tokens in handler.agent_total_tokens.items()
        if agent_name in PUBLIC_AGENT_NAMES and int(total_tokens) > 0
    }
