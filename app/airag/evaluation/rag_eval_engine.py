"""Framework-independent execution of a prepared full response pipeline."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.documents import Document

from app.airag.evaluation.eval_models import EvalCorpus
from app.airag.pipeline_factory import (
    ResponsePipelineConfig,
    normalize_response_pipeline_config,
)

EVALUATION_SAFE_METADATA = (
    "chunk_index",
    "source",
    "score",
    "rerank_score",
    "retrieval_strategy",
    "retrieval_mode",
    "evidence_path",
)


class RagEvaluationCancelled(Exception):
    """Raised when cooperative cancellation is observed by the runtime."""


@dataclass(frozen=True)
class EvaluationProgress:
    stage: str
    progress: float
    completed_examples: int | None = None
    total_examples: int | None = None


@dataclass(frozen=True)
class EvaluationSpecification:
    strategy: str
    chunking: Mapping[str, Any]
    response_pipeline: Mapping[str, Any]
    retrieval: Mapping[str, Any]
    k: int


@dataclass(frozen=True)
class EvaluationResources:
    retriever: Any
    resolved_metadata: Mapping[str, Any]
    cleanup: Callable[[], Any]


@dataclass(frozen=True)
class RankedEvaluationDocument:
    content: str
    rank: int
    metadata: Mapping[str, Any]
    evaluation_ids: tuple[str, ...]


@dataclass(frozen=True)
class PipelineQueryResult:
    evaluation_id: str
    category: str
    answerable: bool
    query: str
    reference_answer: str
    answer: str
    contexts: tuple[str, ...]
    ranked_documents: tuple[RankedEvaluationDocument, ...]


@dataclass(frozen=True)
class PipelineEvaluationResult:
    results: tuple[PipelineQueryResult, ...]
    resolved_pipeline_snapshot: Mapping[str, Any]


ProgressCallback = Callable[[EvaluationProgress], Any]
CancellationCallback = Callable[[], bool | Awaitable[bool]]


class EvaluationResourceAdapter(Protocol):
    async def prepare(
        self,
        *,
        specification: EvaluationSpecification,
        corpus: EvalCorpus,
        run_id: int,
        progress_callback: ProgressCallback | None,
        should_cancel: CancellationCallback | None,
    ) -> EvaluationResources: ...


class ResponsePipeline(Protocol):
    resolved_metadata: Mapping[str, Any]

    async def ainvoke(self, state: Mapping[str, Any]) -> Mapping[str, Any]: ...


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def report_progress(
    callback: ProgressCallback | None,
    stage: str,
    progress: float,
    *,
    completed_examples: int | None = None,
    total_examples: int | None = None,
) -> None:
    if callback is not None:
        await _maybe_await(
            callback(
                EvaluationProgress(
                    stage=stage,
                    progress=progress,
                    completed_examples=completed_examples,
                    total_examples=total_examples,
                )
            )
        )


async def check_cancellation(callback: CancellationCallback | None) -> None:
    if callback is not None and await _maybe_await(callback()):
        raise RagEvaluationCancelled()


def _ranked_documents(final_state: Mapping[str, Any]) -> tuple[RankedEvaluationDocument, ...]:
    context = final_state.get("context")
    if not isinstance(context, str) or not context.strip():
        return ()
    documents = final_state.get("documents", ())
    if not isinstance(documents, (list, tuple)):
        raise ValueError("Response pipeline final documents must be a sequence")
    ranked: list[RankedEvaluationDocument] = []
    for document in documents:
        if not isinstance(document, Document):
            raise ValueError("Response pipeline final documents must be Documents")
        content = str(document.page_content or "")
        raw_ids = document.metadata.get("evaluation_ids", ())
        if not isinstance(raw_ids, (list, tuple)) or not all(
            isinstance(item, str) for item in raw_ids
        ):
            raise ValueError("Final document evaluation_ids must be strings")
        safe_metadata = {
            name: document.metadata[name]
            for name in EVALUATION_SAFE_METADATA
            if name in document.metadata
        }
        ranked.append(
            RankedEvaluationDocument(
                content=content,
                rank=len(ranked) + 1,
                metadata=safe_metadata,
                evaluation_ids=tuple(raw_ids),
            )
        )
    return tuple(ranked)


class FullPipelineEvaluator:
    """Evaluate each suite example through an independently invoked response graph."""

    def __init__(
        self,
        *,
        pipeline_builder: Callable[[Any, ResponsePipelineConfig], ResponsePipeline],
    ) -> None:
        self._pipeline_builder = pipeline_builder

    async def evaluate(
        self,
        *,
        specification: EvaluationSpecification,
        corpus: EvalCorpus,
        adapter: EvaluationResourceAdapter,
        run_id: int,
        progress_callback: ProgressCallback | None = None,
        should_cancel: CancellationCallback | None = None,
    ) -> PipelineEvaluationResult:
        await check_cancellation(should_cancel)
        await report_progress(progress_callback, "preparing", 0.0)
        resources = await adapter.prepare(
            specification=specification,
            corpus=corpus,
            run_id=run_id,
            progress_callback=progress_callback,
            should_cancel=should_cancel,
        )
        try:
            await check_cancellation(should_cancel)
            pipeline_config = normalize_response_pipeline_config(
                specification.strategy,
                specification.response_pipeline,
            )
            pipeline = self._pipeline_builder(resources.retriever, pipeline_config)
            total = len(corpus.examples)
            if total == 0:
                raise ValueError("Evaluation corpus contains no examples")
            await report_progress(
                progress_callback,
                "evaluating",
                0.0,
                completed_examples=0,
                total_examples=total,
            )
            await check_cancellation(should_cancel)
            results: list[PipelineQueryResult] = []
            for completed, example in enumerate(corpus.examples):
                await check_cancellation(should_cancel)
                final_state = await pipeline.ainvoke({"question": example.query})
                if not isinstance(final_state, Mapping):
                    raise ValueError("Response pipeline must return a final state mapping")
                answer = final_state.get("answer")
                if not isinstance(answer, str) or not answer.strip():
                    raise ValueError("Response pipeline final answer must be non-empty")
                documents = _ranked_documents(final_state)
                results.append(
                    PipelineQueryResult(
                        evaluation_id=example.evaluation_id,
                        category=example.category,
                        answerable=example.answerable,
                        query=example.query,
                        reference_answer=example.reference_answer,
                        answer=answer,
                        contexts=tuple(document.content for document in documents),
                        ranked_documents=documents,
                    )
                )
                finished = completed + 1
                await report_progress(
                    progress_callback,
                    "evaluating",
                    finished / total,
                    completed_examples=finished,
                    total_examples=total,
                )
                await check_cancellation(should_cancel)
            snapshot = {
                "suite_version": corpus.suite_version,
                "suite_content_hash": corpus.suite_content_hash,
                **dict(pipeline.resolved_metadata),
                **dict(resources.resolved_metadata),
            }
            snapshot.setdefault(
                "prompt_versions",
                {
                    component: "v1"
                    for component in pipeline_config.llm_components
                },
            )
            return PipelineEvaluationResult(
                results=tuple(results),
                resolved_pipeline_snapshot=snapshot,
            )
        finally:
            try:
                await report_progress(progress_callback, "cleaning_up", 0.0)
            finally:
                await _maybe_await(resources.cleanup())
            await report_progress(progress_callback, "cleaning_up", 1.0)
