"""
Response pipeline factory for CRAG and GraphRAG strategies.
Allows for the construction of a response pipeline with a given 
retriever and configuration. This way the evaluation runtime can be
# generalised and tested against real pipelines used in production, and
# not drift to different graphs or prompt templates.
"""

from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Literal, Mapping

# local imports
from app.airag.chains.crag.crag import CRAGState, make_crag
from app.airag.chains.crag.helpers import make_crag_component_chains
from app.airag.prompts.sys_prompts import (
    ANS_GRADER_PROMPT,
    DOC_GRADE_PROMPT,
    FALLBACK_PROMPT,
    GEN_PROMPT,
    HALL_PROMPT,
    REWRITE_PROMPT,
)
from app.airag.reranking.reranking import (
    DEFAULT_COHERE_MODEL,
    DEFAULT_CROSS_ENCODER_MODEL,
)

PipelineStrategy = Literal["crag", "graphrag"]
PIPELINE_VERSION = "crag_response_v1"
DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
LLM_COMPONENT_NAMES = (
    "document_grader",
    "rewrite",
    "generate",
    "hallucination_grader",
    "answer_grader",
    "fallback",
)
_PROMPTS = {
    "document_grader": DOC_GRADE_PROMPT,
    "rewrite": REWRITE_PROMPT,
    "generate": GEN_PROMPT,
    "hallucination_grader": HALL_PROMPT,
    "answer_grader": ANS_GRADER_PROMPT,
    "fallback": FALLBACK_PROMPT,
}


@dataclass(frozen=True)
class ResponsePipelineConfig:
    """
    Normalized controls for the shared CRAG-based response pipeline.
    """

    strategy: PipelineStrategy
    reranker: str
    top_n: int
    max_rewrite_attempts: int
    llm_components: Mapping[str, Mapping[str, str]]

    def __post_init__(self) -> None:
        """ 
        Post init validator
        """
        if self.strategy not in {"crag", "graphrag"}:
            raise ValueError(f"Unsupported response pipeline strategy: {self.strategy}")
        if not self.reranker.strip():
            raise ValueError("reranker must be a non-empty string")
        if self.top_n < 1:
            raise ValueError("top_n must be at least 1")
        if self.max_rewrite_attempts < 0:
            raise ValueError("max_rewrite_attempts must be at least 0")
        missing = sorted(set(LLM_COMPONENT_NAMES) - set(self.llm_components))
        unknown = sorted(set(self.llm_components) - set(LLM_COMPONENT_NAMES))
        if missing:
            raise ValueError(f"Missing LLM components: {', '.join(missing)}")
        if unknown:
            raise ValueError(f"Unknown LLM components: {', '.join(unknown)}")
        for component, selection in self.llm_components.items():
            if not selection.get("provider", "").strip():
                raise ValueError(f"{component} provider must be a non-empty string")
            if not selection.get("model", "").strip():
                raise ValueError(f"{component} model must be a non-empty string")


@dataclass(frozen=True)
class ResponsePipeline:
    """
    Runnable CRAG response graph plus deterministic, non-secret metadata.
    """

    graph: Any
    resolved_metadata: Mapping[str, Any]

    def invoke(self, state: Any, config: Any = None, **kwargs: Any) -> Any:
        """
        Invoke the response pipeline with the given state and optional 
        configuration.
        Args:
            state (Any): The input state for the response pipeline.
            config (Any, optional): Optional configuration for the 
                response pipeline.
            **kwargs: Additional keyword arguments to pass to the graph 
                invocation.
        Returns:
            Any: The output of the response pipeline invocation.
        """
        if config is None:
            return self.graph.invoke(state, **kwargs)
        return self.graph.invoke(state, config=config, **kwargs)

    async def ainvoke(self, state: Any, config: Any = None, **kwargs: Any) -> Any:
        if config is None:
            return await self.graph.ainvoke(state, **kwargs)
        return await self.graph.ainvoke(state, config=config, **kwargs)


def normalize_response_pipeline_config(
    strategy: str,
    config: Mapping[str, Any] | None,
) -> ResponsePipelineConfig:
    """
    Normalize a CRAG or GraphRAG strategy dictionary for shared construction.
    Args:
        strategy (str): The response pipeline strategy, either "crag" or 
            "graphrag".
        config (Mapping[str, Any] | None): The raw configuration dictionary.
    Returns:
        ResponsePipelineConfig: The normalized response pipeline configuration.
    """
    normalized_strategy = strategy.strip().lower()
    if normalized_strategy not in {"crag", "graphrag"}:
        raise ValueError(f"Unsupported response pipeline strategy: {strategy}")

    # geth the LLM component selections from the config, or use defaults
    values = dict(config or {})
    raw_components = values.get("llm_components") or {}
    components = {
        component: {
            "provider": str(
                raw_components.get(component, {}).get(
                    "provider",
                    DEFAULT_LLM_PROVIDER,
                )
            ),
            "model": str(
                raw_components.get(component, {}).get(
                    "model",
                    DEFAULT_LLM_MODEL,
                )
            ),
        }
        for component in LLM_COMPONENT_NAMES
    }
    if normalized_strategy == "graphrag":
        default_top_n = values.get("evidence_limit", 6)
        default_reranker = "none"
        default_rewrite_attempts = 1
    else:
        default_top_n = 3
        default_reranker = "cross_encoder"
        default_rewrite_attempts = 2

    return ResponsePipelineConfig(
        strategy=normalized_strategy,
        reranker=str(values.get("reranker", default_reranker)),
        top_n=int(values.get("top_n", default_top_n)),
        max_rewrite_attempts=int(
            values.get("max_rewrite_attempts", default_rewrite_attempts)
        ),
        llm_components=components,
    )


def build_response_pipeline(
    retriever: Any,
    config: ResponsePipelineConfig,
) -> ResponsePipeline:
    """
    Build the complete CRAG response graph around an existing retriever.
    Args:
        retriever (Any): The retriever to use for the response pipeline.
        config (ResponsePipelineConfig): The normalized response pipeline 
            configuration.
    Returns:
        ResponsePipeline: The constructed response pipeline with resolved
            metadata.
    """
    component_selections = {
        component: dict(selection)
        for component, selection in config.llm_components.items()
    }
    component_chains = make_crag_component_chains(component_selections)
    graph = make_crag(
        retriever_obj=retriever,
        state_schema=CRAGState,
        max_rewrite_attempts=config.max_rewrite_attempts,
        reranker_name=config.reranker,
        rerank_top_k=config.top_n,
        component_chains=component_chains,
    )
    return ResponsePipeline(
        graph=graph,
        resolved_metadata={
            "pipeline_version": PIPELINE_VERSION,
            "strategy": config.strategy,
            "llm_components": component_selections,
            "prompt_hashes": {
                component: sha256(str(prompt).encode("utf-8")).hexdigest()
                for component, prompt in _PROMPTS.items()
            },
            "reranker": _reranker_metadata(config.reranker),
            "top_n": config.top_n,
            "max_rewrite_attempts": config.max_rewrite_attempts,
        },
    )


def _reranker_metadata(name: str) -> dict[str, str | None]:
    """
    Get metadata for the specified reranker.
    Args:
        name (str): The name of the reranker.
    Returns:
        dict[str, str | None]: A dictionary containing the reranker's 
        implementation and model.
    """
    normalized = name.strip().lower()
    models = {
        "cross_encoder": DEFAULT_CROSS_ENCODER_MODEL,
        "cohere": DEFAULT_COHERE_MODEL,
        "none": None,
    }
    return {
        "implementation": normalized,
        "model": models.get(normalized),
    }
