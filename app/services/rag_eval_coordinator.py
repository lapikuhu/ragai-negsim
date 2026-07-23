"""Single-worker, persistent FIFO coordination for RAG evaluation runs.

The coordinator is application-owned. The supported deployment uses one Uvicorn
worker; multi-process coordinator ownership requires a separate leader-election
design and is intentionally out of scope.
"""

from __future__ import annotations
import asyncio
from collections.abc import Callable, Mapping
from typing import Any

# local imports
from app.airag.evaluation.rag_eval_engine import (
    EvaluationProgress,
    RagEvaluationCancelled,
)
from app.airag.evaluation.rag_eval_helpers import create_eval_corpus
from app.airag.evaluation.rag_eval_metrics import PipelineResultScorer
from app.airag.evaluation.rag_eval_runtime import (
    cleanup_rag_eval_graph_scope,
    create_rag_eval_runtime,
)
from app.airag.evaluation.ragas_helpers import RagasEvaluator
from app.db.db import AsyncSessionLocal
from app.repositories import rag_eval_repo
from app.repositories.rag_eval_repo import RagEvalFinalizationCancelled
from app.schemas.rag_eval_schemas import (
    RagEvalConfigurationCreateRequest,
    RagEvalFinalChunk,
    RagEvalQueryResultCreate,
)


_STAGE_PROGRESS_RANGES = {
    "preparing": (0.0, 5.0),
    "chunking": (5.0, 15.0),
    "building_index": (15.0, 25.0),
    "building_graph": (15.0, 25.0),
    "evaluating": (25.0, 80.0),
    "cleaning_up": (80.0, 85.0),
}


def _overall_progress(stage: str, local_progress: float) -> float:
    start, end = _STAGE_PROGRESS_RANGES.get(stage, (0.0, 100.0))
    bounded = min(1.0, max(0.0, float(local_progress)))
    return start + ((end - start) * bounded)


def _safe_failure_message(stage: str) -> str:
    safe_stage = stage if stage in rag_eval_repo.RAG_EVAL_RUN_STAGES else "execution"
    return f"RAG evaluation failed during {safe_stage}."


def _query_rows(scored: Any) -> list[RagEvalQueryResultCreate]:
    """
    Append the scores to the query results.
    Args:
        scored: The scored evaluation results.
    Returns:
        A list of RagEvalQueryResultCreate objects with the scores appended.
    """
    rows: list[RagEvalQueryResultCreate] = []
    for result in scored.results:
        final_chunks = [
            RagEvalFinalChunk(
                rank=rank,
                content=document.content,
                metadata=dict(document.metadata),
            )
            for rank, document in enumerate(result.ranked_documents, start=1)
        ]
        rows.append(
            RagEvalQueryResultCreate(
                example_id=result.evaluation_id,
                category=result.category,
                answerable=result.answerable,
                query=result.query,
                reference_answer=result.reference_answer,
                actual_answer=result.answer,
                final_chunks=final_chunks,
                first_relevant_rank=result.first_relevant_rank,
                hit_at_k=result.hit_at_k,
                mrr_at_k=result.mrr_at_k,
                successful_abstention=result.successful_abstention,
                false_positive_context=result.false_positive_context,
                faithfulness=result.faithfulness,
                answer_relevancy=result.answer_relevancy,
                context_precision=result.context_precision,
                context_recall=result.context_recall,
                answer_correctness=result.answer_correctness,
            )
        )
    return rows


class RagEvalCoordinator:
    """
    Own one persistent FIFO execution loop for this application process.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] = AsyncSessionLocal,
        repository: Any = rag_eval_repo,
        corpus_factory: Callable[[], Any] = create_eval_corpus,
        runtime_factory: Callable[[], Any] = create_rag_eval_runtime,
        ragas_factory: Callable[[Mapping[str, Any]], Any] | None = None,
        scorer_factory: Callable[[Any], Any] = PipelineResultScorer,
        graph_cleanup: Callable[[int], Any] = cleanup_rag_eval_graph_scope,
        cleanup_retry_seconds: float = 5.0,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository # Get all the repo methods from rag_eval_repo
        self._corpus_factory = corpus_factory
        self._runtime_factory = runtime_factory
        self._ragas_factory = ragas_factory or (
            RagasEvaluator.from_normalized_configuration
        )
        self._scorer_factory = scorer_factory
        self._graph_cleanup = graph_cleanup
        self._cleanup_retry_seconds = cleanup_retry_seconds
        self._wake_event = asyncio.Event()
        self._stopping = False
        self._worker: asyncio.Task[None] | None = None
        self._last_recovery_blocked = False

    @property
    def is_running(self) -> bool:
        """
        Check if the coordinator is currently running.
        Returns:
            True if the coordinator is running, False otherwise.
        """
        return self._worker is not None and not self._worker.done()

    async def start(self) -> asyncio.Task[None]:
        """
        Start the coordinator if it is not already running.
        Returns:
            The asyncio Task representing the coordinator's run loop."""
        if self.is_running:
            assert self._worker is not None
            return self._worker
        self._stopping = False
        self._worker = asyncio.create_task(
            self._run_loop(),
            name="rag-eval-coordinator",
        )
        return self._worker

    async def stop(self) -> None:
        """
        Stop the coordinator.
        Args:
            None
        Returns:
            None
        """
        worker = self._worker
        if worker is None:
            return
        self._stopping = True
        self._wake_event.set()
        await worker
        self._worker = None

    def wake(self) -> None:
        self._wake_event.set()

    async def _run_loop(self) -> None:
        """
        Run the coordinator loop until it is stopped. The loop will 
        recover interrupted runs, claim and execute queued runs, and 
        wait for new runs to be enqueued.
        Returns:
            None
        """
        while not self._stopping:
            self._wake_event.clear()
            processed = await self.process_once()
            if self._stopping:
                break
            if self._last_recovery_blocked:
                try:
                    await asyncio.wait_for(
                        self._wake_event.wait(),
                        timeout=self._cleanup_retry_seconds,
                    )
                except TimeoutError:
                    pass
            elif not processed:
                await self._wake_event.wait()

    async def process_once(self) -> bool:
        """
        Recover interrupted work, then claim and execute at most one queued run.
        Returns:
            True if a run was processed, False otherwise.
        """
        recovered, blocked = await self._recover_interrupted()
        self._last_recovery_blocked = blocked
        if blocked:
            return True

        async with self._session_factory() as session:
            run = await self._repository.claim_next_rag_eval_run(session)
            if run is None:
                return False
            await self._execute(run, session)
        return True or recovered

    async def _recover_interrupted(self) -> tuple[bool, bool]:
        """
        Recover interrupted runs, cleaning up any resources if necessary.
        Returns:
            A tuple (recovered, blocked) where:
            - recovered is True if any interrupted runs were recovered.
            - blocked is True if recovery was blocked due to a cleanup failure.
        """
        recovered = False
        async with self._session_factory() as session:
            interrupted = await self._repository.list_interrupted_rag_eval_runs(
                session
            )
            for run in interrupted:
                recovered = True
                strategy = (
                    run.configuration_snapshot.get("rag", {}).get("strategy") # Get the config strategy for the run
                )
                if strategy == "graphrag":
                    try:
                        await self._graph_cleanup(run.id)
                    except Exception: # If something happens, return blocked
                        await self._repository.update_rag_eval_run_progress(
                            run,
                            stage="cleanup_pending",
                            progress=getattr(run, "progress", 0.0),
                            completed_examples=getattr(
                                run, "completed_examples", 0
                            ),
                            total_examples=getattr(run, "total_examples", 0),
                            session=session,
                        )
                        return recovered, True
                await self._repository.mark_rag_eval_run_failed(
                    run,
                    "RAG evaluation was interrupted by application restart.",
                    session,
                )
        return recovered, False

    async def _is_cancel_requested(self, run_id: int) -> bool:
        """
        Check if a cancellation has been requested for the given run.
        Args:
            run_id (int): The ID of the RAG evaluation run.
        Returns:
            True if cancellation has been requested, False otherwise.
            """
        async with self._session_factory() as session:
            current = await self._repository.get_rag_eval_run_by_id(
                run_id, session
            )
            return bool(current is None or current.cancel_requested)

    async def _mark_cancelled(self, run: Any, session: Any) -> None:
        """
        Mark the given run as cancelled if it is currently running.
        Args:
            run (Any): The RAG evaluation run to mark as cancelled.
            session (Any): The database session.
        Returns:
            None
        """
        current = await self._repository.get_rag_eval_run_by_id(run.id, session)
        if current is not None and current.status == "running":
            await self._repository.mark_rag_eval_run_cancelled(current, session)

    async def _execute(self, run: Any, session: Any) -> None:
        active_stage = "preparing"
        strategy: str | None = None

        async def should_cancel() -> bool:
            return await self._is_cancel_requested(run.id)

        async def progress_callback(update: EvaluationProgress) -> None:
            nonlocal active_stage # Allowing active_stage to be updated within the callback
            active_stage = update.stage
            # Persist the progress update to the database
            await self._repository.update_rag_eval_run_progress(
                run,
                stage=update.stage,
                progress=_overall_progress(update.stage, update.progress),
                completed_examples=(
                    update.completed_examples
                    if update.completed_examples is not None
                    else getattr(run, "completed_examples", 0)
                ),
                total_examples=(
                    update.total_examples
                    if update.total_examples is not None
                    else run.total_examples
                ),
                session=session,
            )
        # Validate the configuration and check if the the eval suite has
        # changed since the run was queued.
        try:
            configuration = RagEvalConfigurationCreateRequest.model_validate(
                run.configuration_snapshot
            )
            strategy = configuration.rag.strategy
            corpus = self._corpus_factory()
            if (
                corpus.suite_version != run.suite_version
                or corpus.suite_content_hash != run.suite_content_hash
            ):
                raise ValueError("Evaluation suite changed after the run was queued")

            runtime_result = await self._runtime_factory().run(
                run_id=run.id,
                configuration=configuration,
                corpus=corpus,
                progress_callback=progress_callback,
                should_cancel=should_cancel,
            )
            if await should_cancel():
                raise RagEvaluationCancelled()

            active_stage = "scoring"
            await self._repository.update_rag_eval_run_progress(
                run,
                stage="scoring",
                progress=85.0,
                completed_examples=run.total_examples,
                total_examples=run.total_examples,
                session=session,
            )
            ragas_evaluator = self._ragas_factory(run.configuration_snapshot)
            scored = await self._scorer_factory(ragas_evaluator).score(
                runtime_result,
                k=configuration.metrics.k,
                should_cancel=should_cancel,
            )
            if await should_cancel():
                raise RagEvaluationCancelled()

            active_stage = "persisting"
            await self._repository.update_rag_eval_run_progress(
                run,
                stage="persisting",
                progress=95.0,
                completed_examples=run.total_examples,
                total_examples=run.total_examples,
                session=session,
            )
            if await should_cancel():
                raise RagEvaluationCancelled()
            await self._repository.finalize_rag_eval_run_success(
                run,
                _query_rows(scored),
                overall_metrics=dict(scored.overall_metrics),
                category_metrics={
                    key: dict(value)
                    for key, value in scored.category_metrics.items()
                },
                resolved_pipeline_snapshot=dict(
                    scored.resolved_pipeline_snapshot
                ),
                session=session,
            )
        except RagEvalFinalizationCancelled:
            await self._mark_cancelled(run, session)
        except RagEvaluationCancelled:
            await self._mark_cancelled(run, session)
        except Exception as exc:
            if active_stage == "scoring":
                print(
                    "[rag-eval] coordinator scoring failed "
                    f"error={type(exc).__name__}: {exc}"
                )
            if strategy == "graphrag" and active_stage == "cleaning_up":
                self._last_recovery_blocked = True
                await self._repository.update_rag_eval_run_progress(
                    run,
                    stage="cleanup_pending",
                    progress=getattr(run, "progress", 0.0),
                    completed_examples=getattr(run, "completed_examples", 0),
                    total_examples=getattr(run, "total_examples", 0),
                    session=session,
                )
                return
            current = await self._repository.get_rag_eval_run_by_id(
                run.id, session
            )
            if current is not None and current.status == "running":
                await self._repository.mark_rag_eval_run_failed(
                    current,
                    _safe_failure_message(active_stage),
                    session,
                )


rag_eval_coordinator = RagEvalCoordinator()
