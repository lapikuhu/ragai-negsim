import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app.airag.evaluation.eval_models import EvalCorpus
from app.airag.evaluation.rag_eval_engine import (
    EvaluationProgress,
    PipelineEvaluationResult,
    PipelineQueryResult,
    RagEvaluationCancelled,
    RankedEvaluationDocument,
)
from app.airag.evaluation.rag_eval_metrics import (
    ScoredPipelineEvaluationResult,
    ScoredPipelineQueryResult,
)


def _configuration_snapshot(*, strategy="crag"):
    llm = {"provider": "openai", "model": "gpt-4o-mini"}
    rag = {
        "strategy": strategy,
        "document_grader": llm,
        "query_rewriter": llm,
        "answer_generator": llm,
        "hallucination_grader": llm,
        "answer_grader": llm,
        "fallback_generator": llm,
    }
    if strategy == "crag":
        rag.update(
            retrieval_embedding_model="text-embedding-3-small",
            top_k=4,
            reranker="cross_encoder",
            top_n=3,
            rewrite_limit=2,
        )
    else:
        rag.update(
            extraction_llm=llm,
            graph_embedding_model="text-embedding-3-small",
            max_paths_per_chunk=10,
            retrieval_mode="semantic",
            evidence_limit=6,
            traversal_depth=2,
            rrf_constant=60,
        )
    return {
        "name": "baseline evaluation",
        "chunking": {
            "strategy": "recursive",
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "separators": ["\n\n", "\n", " ", ""],
        },
        "rag": rag,
        "metrics": {
            "k": 3,
            "ragas_judge": llm,
            "judge_embedding_model": "text-embedding-3-small",
        },
    }


def _run(run_id=7, *, strategy="crag", status="running", stage="preparing"):
    return SimpleNamespace(
        id=run_id,
        status=status,
        stage=stage,
        cancel_requested=False,
        configuration_snapshot=_configuration_snapshot(strategy=strategy),
        suite_version="rag-eval-v1",
        suite_content_hash="content-hash",
        total_examples=1,
    )


def _corpus():
    return EvalCorpus(
        documents=(),
        eval_documents=(),
        support_spans=(),
        examples=(),
        suite_version="rag-eval-v1",
        suite_content_hash="content-hash",
    )


class _Session:
    async def refresh(self, _run):
        return None


def _session_factory():
    @asynccontextmanager
    async def context():
        yield _Session()

    return context()


def _pipeline_result():
    document = RankedEvaluationDocument(
        content="safe context",
        rank=1,
        metadata={"source": "suite.md", "score": 0.8},
        evaluation_ids=("ex-1",),
    )
    row = PipelineQueryResult(
        evaluation_id="ex-1",
        category="direct_retrieval",
        answerable=True,
        query="Question?",
        reference_answer="Reference",
        answer="Actual",
        contexts=("safe context",),
        ranked_documents=(document,),
    )
    return PipelineEvaluationResult(
        results=(row,),
        resolved_pipeline_snapshot={"pipeline": "resolved"},
    )


def _scored_result():
    source = _pipeline_result()
    row = ScoredPipelineQueryResult(
        evaluation_id="ex-1",
        category="direct_retrieval",
        answerable=True,
        query="Question?",
        reference_answer="Reference",
        answer="Actual",
        ranked_documents=source.results[0].ranked_documents,
        first_relevant_rank=1,
        hit_at_k=True,
        mrr_at_k=1.0,
        successful_abstention=None,
        false_positive_context=None,
        faithfulness=0.9,
        answer_relevancy=0.8,
        context_precision=0.7,
        context_recall=0.6,
        answer_correctness=0.5,
    )
    return ScoredPipelineEvaluationResult(
        results=(row,),
        overall_metrics={"overall_score": 0.75},
        category_metrics={"direct_retrieval": {"overall_score": 0.75}},
        resolved_pipeline_snapshot=source.resolved_pipeline_snapshot,
    )


@pytest.mark.asyncio
async def test_coordinator_runs_rich_pipeline_scores_and_finalizes_once_atomically():
    from app.services.rag_eval_coordinator import RagEvalCoordinator

    run = _run()
    events = []

    class Repository:
        async def list_interrupted_rag_eval_runs(self, _session):
            return []

        async def claim_next_rag_eval_run(self, _session):
            events.append("claim")
            return run

        async def update_rag_eval_run_progress(self, active, **values):
            events.append(("progress", values["stage"], values["progress"]))
            active.stage = values["stage"]
            return active

        async def get_rag_eval_run_by_id(self, _run_id, _session):
            return run

        async def finalize_rag_eval_run_success(self, active, rows, **values):
            events.append(("finalize", list(rows), values))
            active.status = "completed"
            return active

    class Runtime:
        async def run(self, **values):
            events.append(("runtime", values["configuration"], values["corpus"]))
            await values["progress_callback"](
                EvaluationProgress("evaluating", 0.5, 1, 1)
            )
            return _pipeline_result()

    class Scorer:
        async def score(self, evaluation, **values):
            events.append(("score", evaluation, values["k"]))
            return _scored_result()

    coordinator = RagEvalCoordinator(
        session_factory=_session_factory,
        repository=Repository(),
        corpus_factory=_corpus,
        runtime_factory=lambda: Runtime(),
        ragas_factory=lambda _configuration: object(),
        scorer_factory=lambda _ragas: Scorer(),
    )

    assert await coordinator.process_once() is True

    finalizations = [event for event in events if event[0] == "finalize"]
    assert len(finalizations) == 1
    row = finalizations[0][1][0]
    assert row.example_id == "ex-1"
    assert [chunk.rank for chunk in row.final_chunks] == [1]
    assert row.final_chunks[0].metadata.source == "suite.md"
    assert finalizations[0][2]["overall_metrics"] == {"overall_score": 0.75}
    assert events.index("claim") < next(
        index for index, event in enumerate(events) if event[0] == "runtime"
    )
    assert next(
        index for index, event in enumerate(events) if event[0] == "runtime"
    ) < next(index for index, event in enumerate(events) if event[0] == "score")


@pytest.mark.asyncio
async def test_progress_and_running_cancellation_are_cooperative_and_never_finalize():
    from app.services.rag_eval_coordinator import RagEvalCoordinator

    run = _run()
    progress = []
    finalized = False
    cancelled = []

    class Repository:
        async def list_interrupted_rag_eval_runs(self, _session):
            return []

        async def claim_next_rag_eval_run(self, _session):
            return run

        async def update_rag_eval_run_progress(self, active, **values):
            progress.append((values["stage"], values["completed_examples"]))
            active.stage = values["stage"]
            return active

        async def get_rag_eval_run_by_id(self, _run_id, _session):
            return SimpleNamespace(
                id=run.id,
                status="running",
                cancel_requested=True,
            )

        async def mark_rag_eval_run_cancelled(self, active, _session):
            cancelled.append(active.id)
            active.status = "cancelled"
            return active

        async def finalize_rag_eval_run_success(self, *_args, **_kwargs):
            nonlocal finalized
            finalized = True

    class Runtime:
        async def run(self, **values):
            await values["progress_callback"](
                EvaluationProgress("chunking", 1.0, 0, 1)
            )
            if await values["should_cancel"]():
                raise RagEvaluationCancelled()
            raise AssertionError("cancellation was not observed")

    coordinator = RagEvalCoordinator(
        session_factory=_session_factory,
        repository=Repository(),
        corpus_factory=_corpus,
        runtime_factory=lambda: Runtime(),
        ragas_factory=lambda _configuration: object(),
        scorer_factory=lambda _ragas: object(),
    )

    await coordinator.process_once()

    assert progress == [("chunking", 0)]
    assert cancelled == [run.id]
    assert finalized is False


@pytest.mark.asyncio
async def test_failure_is_sanitized_and_has_no_partial_finalization():
    from app.services.rag_eval_coordinator import RagEvalCoordinator

    run = _run()
    failures = []

    class Repository:
        async def list_interrupted_rag_eval_runs(self, _session):
            return []

        async def claim_next_rag_eval_run(self, _session):
            return run

        async def update_rag_eval_run_progress(self, active, **values):
            active.stage = values["stage"]
            return active

        async def get_rag_eval_run_by_id(self, _run_id, _session):
            return run

        async def mark_rag_eval_run_failed(self, active, detail, _session):
            failures.append(detail)
            active.status = "failed"
            return active

        async def finalize_rag_eval_run_success(self, *_args, **_kwargs):
            raise AssertionError("failed runs must not persist partial results")

    class Runtime:
        async def run(self, **_values):
            raise RuntimeError("api_key=super-secret provider payload")

    coordinator = RagEvalCoordinator(
        session_factory=_session_factory,
        repository=Repository(),
        corpus_factory=_corpus,
        runtime_factory=lambda: Runtime(),
        ragas_factory=lambda _configuration: object(),
        scorer_factory=lambda _ragas: object(),
    )

    await coordinator.process_once()

    assert failures == ["RAG evaluation failed during preparing."]
    assert "secret" not in failures[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_requested", [False, True])
async def test_live_graphrag_cleanup_failure_becomes_cleanup_pending(
    cancel_requested,
):
    from app.services.rag_eval_coordinator import RagEvalCoordinator

    run = _run(strategy="graphrag")
    stages = []
    failures = []

    class Repository:
        async def list_interrupted_rag_eval_runs(self, _session):
            return []

        async def claim_next_rag_eval_run(self, _session):
            return run

        async def update_rag_eval_run_progress(self, active, **values):
            stages.append(values["stage"])
            active.stage = values["stage"]
            return active

        async def get_rag_eval_run_by_id(self, _run_id, _session):
            return SimpleNamespace(
                id=run.id,
                status="running",
                cancel_requested=cancel_requested,
            )

        async def mark_rag_eval_run_failed(self, _active, detail, _session):
            failures.append(detail)

    class Runtime:
        async def run(self, **values):
            await values["progress_callback"](
                EvaluationProgress("cleaning_up", 0.0, 0, 1)
            )
            raise RuntimeError("cleanup masked the original runtime outcome")

    coordinator = RagEvalCoordinator(
        session_factory=_session_factory,
        repository=Repository(),
        corpus_factory=_corpus,
        runtime_factory=lambda: Runtime(),
    )

    await coordinator.process_once()

    assert stages == ["cleaning_up", "cleanup_pending"]
    assert failures == []


@pytest.mark.asyncio
async def test_live_crag_cleanup_failure_is_sanitized_and_failed():
    from app.services.rag_eval_coordinator import RagEvalCoordinator

    run = _run(strategy="crag")
    failures = []

    class Repository:
        async def list_interrupted_rag_eval_runs(self, _session):
            return []

        async def claim_next_rag_eval_run(self, _session):
            return run

        async def update_rag_eval_run_progress(self, active, **values):
            active.stage = values["stage"]
            return active

        async def get_rag_eval_run_by_id(self, _run_id, _session):
            return run

        async def mark_rag_eval_run_failed(self, _active, detail, _session):
            failures.append(detail)

    class Runtime:
        async def run(self, **values):
            await values["progress_callback"](
                EvaluationProgress("cleaning_up", 0.0, 0, 1)
            )
            raise RuntimeError("provider payload")

    coordinator = RagEvalCoordinator(
        session_factory=_session_factory,
        repository=Repository(),
        corpus_factory=_corpus,
        runtime_factory=lambda: Runtime(),
    )

    await coordinator.process_once()

    assert failures == ["RAG evaluation failed during cleaning_up."]


@pytest.mark.asyncio
async def test_cancellation_requested_at_persisting_boundary_prevents_finalization():
    from app.services.rag_eval_coordinator import RagEvalCoordinator

    run = _run()
    cancel_checks = 0
    finalized = False
    cancelled = []

    class Repository:
        async def list_interrupted_rag_eval_runs(self, _session):
            return []

        async def claim_next_rag_eval_run(self, _session):
            return run

        async def update_rag_eval_run_progress(self, active, **values):
            active.stage = values["stage"]
            return active

        async def get_rag_eval_run_by_id(self, _run_id, _session):
            nonlocal cancel_checks
            cancel_checks += 1
            requested = cancel_checks >= 3
            return SimpleNamespace(
                id=run.id,
                status="running",
                cancel_requested=requested,
            )

        async def mark_rag_eval_run_cancelled(self, active, _session):
            cancelled.append(active.id)

        async def finalize_rag_eval_run_success(self, *_args, **_kwargs):
            nonlocal finalized
            finalized = True

    class Runtime:
        async def run(self, **_values):
            return _pipeline_result()

    class Scorer:
        async def score(self, _evaluation, **_values):
            return _scored_result()

    coordinator = RagEvalCoordinator(
        session_factory=_session_factory,
        repository=Repository(),
        corpus_factory=_corpus,
        runtime_factory=lambda: Runtime(),
        ragas_factory=lambda _configuration: object(),
        scorer_factory=lambda _ragas: Scorer(),
    )

    await coordinator.process_once()

    assert cancelled == [run.id]
    assert finalized is False


@pytest.mark.asyncio
async def test_finalizer_late_cancellation_race_is_marked_cancelled_not_failed():
    from app.repositories.rag_eval_repo import RagEvalFinalizationCancelled
    from app.services.rag_eval_coordinator import RagEvalCoordinator

    run = _run()
    cancelled = []
    failed = []

    class Repository:
        async def list_interrupted_rag_eval_runs(self, _session):
            return []

        async def claim_next_rag_eval_run(self, _session):
            return run

        async def update_rag_eval_run_progress(self, active, **values):
            active.stage = values["stage"]
            return active

        async def get_rag_eval_run_by_id(self, _run_id, _session):
            return SimpleNamespace(
                id=run.id,
                status="running",
                cancel_requested=True,
            )

        async def finalize_rag_eval_run_success(self, *_args, **_kwargs):
            raise RagEvalFinalizationCancelled()

        async def mark_rag_eval_run_cancelled(self, active, _session):
            cancelled.append(active.id)

        async def mark_rag_eval_run_failed(self, _active, detail, _session):
            failed.append(detail)

    class Runtime:
        async def run(self, **_values):
            return _pipeline_result()

    class Scorer:
        async def score(self, _evaluation, **_values):
            return _scored_result()

    cancel_checks = 0

    async def cancellation_after_last_coordinator_check(_run_id):
        nonlocal cancel_checks
        cancel_checks += 1
        return False

    coordinator = RagEvalCoordinator(
        session_factory=_session_factory,
        repository=Repository(),
        corpus_factory=_corpus,
        runtime_factory=lambda: Runtime(),
        ragas_factory=lambda _configuration: object(),
        scorer_factory=lambda _ragas: Scorer(),
    )
    coordinator._is_cancel_requested = cancellation_after_last_coordinator_check

    await coordinator.process_once()

    assert cancel_checks == 3
    assert cancelled == [run.id]
    assert failed == []


@pytest.mark.asyncio
async def test_cleanup_pending_blocks_claims_until_graph_cleanup_succeeds():
    from app.services.rag_eval_coordinator import RagEvalCoordinator

    interrupted = _run(strategy="graphrag", stage="cleanup_pending")
    cleanups = 0
    claims = 0

    class Repository:
        async def list_interrupted_rag_eval_runs(self, _session):
            return [interrupted] if interrupted.status == "running" else []

        async def update_rag_eval_run_progress(self, active, **values):
            active.stage = values["stage"]
            return active

        async def mark_rag_eval_run_failed(self, active, _detail, _session):
            active.status = "failed"
            return active

        async def claim_next_rag_eval_run(self, _session):
            nonlocal claims
            claims += 1
            return None

    async def cleanup(_run_id):
        nonlocal cleanups
        cleanups += 1
        if cleanups == 1:
            raise RuntimeError("temporarily unavailable")

    coordinator = RagEvalCoordinator(
        session_factory=_session_factory,
        repository=Repository(),
        graph_cleanup=cleanup,
    )

    assert await coordinator.process_once() is True
    assert claims == 0
    assert interrupted.stage == "cleanup_pending"

    assert await coordinator.process_once() is False
    assert cleanups == 2
    assert claims == 1
    assert interrupted.status == "failed"


@pytest.mark.asyncio
async def test_start_stop_owns_one_worker_and_does_not_fail_queued_work():
    from app.services.rag_eval_coordinator import RagEvalCoordinator

    claims = 0
    entered_claim = asyncio.Event()

    class Repository:
        async def list_interrupted_rag_eval_runs(self, _session):
            return []

        async def claim_next_rag_eval_run(self, _session):
            nonlocal claims
            claims += 1
            entered_claim.set()
            return None

    coordinator = RagEvalCoordinator(
        session_factory=_session_factory,
        repository=Repository(),
    )
    first = await coordinator.start()
    second = await coordinator.start()
    await asyncio.wait_for(entered_claim.wait(), timeout=1)
    await coordinator.stop()

    assert first is second
    assert claims >= 1
    assert coordinator.is_running is False


@pytest.mark.asyncio
async def test_worker_executes_claimed_runs_strictly_one_at_a_time():
    from app.services.rag_eval_coordinator import RagEvalCoordinator

    queued = [_run(1), _run(2)]
    by_id = {run.id: run for run in queued}
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    second_finished = asyncio.Event()
    active = 0
    maximum_active = 0

    class Repository:
        async def list_interrupted_rag_eval_runs(self, _session):
            return []

        async def claim_next_rag_eval_run(self, _session):
            return queued.pop(0) if queued else None

        async def update_rag_eval_run_progress(self, run, **values):
            run.stage = values["stage"]
            return run

        async def get_rag_eval_run_by_id(self, run_id, _session):
            return by_id[run_id]

        async def finalize_rag_eval_run_success(self, run, _rows, **_values):
            run.status = "completed"
            if run.id == 2:
                second_finished.set()
            return run

    class Runtime:
        async def run(self, *, run_id, **_values):
            nonlocal active, maximum_active
            active += 1
            maximum_active = max(maximum_active, active)
            if run_id == 1:
                first_entered.set()
                await release_first.wait()
            active -= 1
            return _pipeline_result()

    class Scorer:
        async def score(self, _evaluation, **_values):
            return _scored_result()

    coordinator = RagEvalCoordinator(
        session_factory=_session_factory,
        repository=Repository(),
        corpus_factory=_corpus,
        runtime_factory=lambda: Runtime(),
        ragas_factory=lambda _configuration: object(),
        scorer_factory=lambda _ragas: Scorer(),
    )

    await coordinator.start()
    await asyncio.wait_for(first_entered.wait(), timeout=1)
    coordinator.wake()
    coordinator.wake()
    await asyncio.sleep(0)
    assert active == 1

    release_first.set()
    await asyncio.wait_for(second_finished.wait(), timeout=1)
    await coordinator.stop()

    assert maximum_active == 1
    assert [by_id[1].status, by_id[2].status] == ["completed", "completed"]
