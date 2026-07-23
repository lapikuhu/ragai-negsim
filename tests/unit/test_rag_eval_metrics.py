from __future__ import annotations

import math
from pathlib import Path

import pytest

from app.airag.evaluation.rag_eval_engine import (
    PipelineEvaluationResult,
    PipelineQueryResult,
    RagEvaluationCancelled,
    RankedEvaluationDocument,
)
from app.airag.evaluation.rag_eval_metrics import (
    PipelineResultScorer,
    aggregate_scored_results,
)


METRIC_SCORES = {
    "faithfulness": 0.9,
    "answer_relevancy": 0.8,
    "context_precision": 0.7,
    "context_recall": 0.6,
    "answer_correctness": 0.5,
}


def _document(rank: int, *evaluation_ids: str) -> RankedEvaluationDocument:
    return RankedEvaluationDocument(
        content=f"context {rank}",
        rank=rank,
        metadata={"source": f"source-{rank}.md"},
        evaluation_ids=tuple(evaluation_ids),
    )


def _query(
    evaluation_id: str = "example-1",
    *,
    category: str = "direct_retrieval",
    answerable: bool = True,
    documents: tuple[RankedEvaluationDocument, ...] = (),
) -> PipelineQueryResult:
    return PipelineQueryResult(
        evaluation_id=evaluation_id,
        category=category,
        answerable=answerable,
        query="Question?",
        reference_answer="Reference",
        answer="Actual",
        contexts=tuple(document.content for document in documents),
        ranked_documents=documents,
    )


class _Ragas:
    def __init__(self, scores=None):
        self.scores = METRIC_SCORES if scores is None else scores
        self.calls = []

    async def score_query(self, result, *, should_cancel=None):
        self.calls.append(result)
        return dict(self.scores)


@pytest.mark.asyncio
async def test_hit_and_mrr_use_only_final_ranked_documents_and_k_cutoff():
    stale_raw_retrieval_id = "example-1"
    del stale_raw_retrieval_id  # No raw retrieval input exists on the scorer API.
    query = _query(
        documents=(
            _document(1, "other"),
            _document(2, "other"),
            _document(3, "example-1"),
        )
    )

    scored = await PipelineResultScorer(_Ragas()).score(
        PipelineEvaluationResult((query,), {}), k=2
    )

    row = scored.results[0]
    assert row.hit_at_k is False
    assert row.first_relevant_rank is None
    assert row.mrr_at_k == 0.0
    assert row.ranked_documents == query.ranked_documents


@pytest.mark.asyncio
async def test_multi_hop_uses_first_relevant_document_semantics():
    query = _query(
        evaluation_id="multi-1",
        category="relational_multi_hop",
        documents=(
            _document(10, "other"),
            _document(20, "multi-1", "bridge-evidence"),
            _document(30, "multi-1"),
        ),
    )

    row = (
        await PipelineResultScorer(_Ragas()).score(
            PipelineEvaluationResult((query,), {}), k=3
        )
    ).results[0]

    assert row.first_relevant_rank == 2
    assert row.hit_at_k is True
    assert row.mrr_at_k == 0.5


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("documents", "successful_abstention", "false_positive_context"),
    [
        ((), True, False),
        ((_document(1, "other"),), False, True),
    ],
)
async def test_unanswerable_metrics_are_null_and_context_presence_is_deterministic(
    documents, successful_abstention, false_positive_context
):
    query = _query(
        category="unanswerable", answerable=False, documents=documents
    )

    row = (
        await PipelineResultScorer(_Ragas()).score(
            PipelineEvaluationResult((query,), {}), k=2
        )
    ).results[0]

    assert row.hit_at_k is None
    assert row.first_relevant_rank is None
    assert row.mrr_at_k is None
    assert row.successful_abstention is successful_abstention
    assert row.false_positive_context is false_positive_context


@pytest.mark.asyncio
async def test_scorer_buffers_complete_rows_and_aggregates_means_and_scores():
    queries = (
        _query("a", documents=(_document(1, "a"),)),
        _query("b", documents=(_document(1, "other"),)),
        _query(
            "u",
            category="unanswerable",
            answerable=False,
            documents=(_document(1, "other"),),
        ),
    )

    scored = await PipelineResultScorer(_Ragas()).score(
        PipelineEvaluationResult(queries, {"pipeline": "v1"}), k=1
    )

    assert scored.overall_metrics["hit_at_k"] == 0.5
    assert scored.overall_metrics["mrr_at_k"] == 0.5
    assert scored.overall_metrics["successful_abstention"] == 0.0
    assert scored.overall_metrics["false_positive_context_rate"] == 1.0
    assert scored.overall_metrics["faithfulness"] == 0.9
    assert scored.overall_metrics["overall_score"] == pytest.approx(
        (0.5 + 0.5 + 0.0 + 0.0 + sum(METRIC_SCORES.values())) / 9
    )
    direct = scored.category_metrics["direct_retrieval"]
    assert direct["overall_score"] == pytest.approx(
        (0.5 + 0.5 + sum(METRIC_SCORES.values())) / 7
    )
    unanswerable = scored.category_metrics["unanswerable"]
    assert unanswerable["overall_score"] == pytest.approx(
        (0.0 + 0.0 + sum(METRIC_SCORES.values())) / 7
    )
    assert scored.resolved_pipeline_snapshot == {"pipeline": "v1"}
    assert [row.evaluation_id for row in scored.results] == ["a", "b", "u"]


@pytest.mark.asyncio
async def test_scorer_clamps_tiny_floating_point_noise_at_score_boundaries():
    scores = {
        **METRIC_SCORES,
        "faithfulness": -0.0000000000000002,
        "answer_relevancy": 1.0000000000000002,
    }

    scored = await PipelineResultScorer(_Ragas(scores)).score(
        PipelineEvaluationResult((_query("boundary-noise"),), {}), k=1
    )

    assert scored.results[0].faithfulness == 0.0
    assert scored.results[0].answer_relevancy == 1.0


@pytest.mark.asyncio
async def test_cancellation_is_checked_between_query_metric_suites():
    checks = 0

    async def should_cancel():
        nonlocal checks
        checks += 1
        return checks >= 2

    with pytest.raises(RagEvaluationCancelled):
        await PipelineResultScorer(_Ragas()).score(
            PipelineEvaluationResult((_query("a"), _query("b")), {}),
            k=1,
            should_cancel=should_cancel,
        )


@pytest.mark.asyncio
async def test_scorer_rejects_empty_results_and_missing_or_invalid_ragas_scores():
    scorer = PipelineResultScorer(_Ragas())
    with pytest.raises(ValueError, match="empty"):
        await scorer.score(PipelineEvaluationResult((), {}), k=1)

    invalid_cases = (
        {name: value for name, value in METRIC_SCORES.items() if name != "faithfulness"},
        {**METRIC_SCORES, "faithfulness": math.nan},
        {**METRIC_SCORES, "faithfulness": math.inf},
        {**METRIC_SCORES, "faithfulness": -0.000000001},
        {**METRIC_SCORES, "faithfulness": 1.000000001},
        {**METRIC_SCORES, "faithfulness": -0.1},
        {**METRIC_SCORES, "faithfulness": 1.1},
    )
    for scores in invalid_cases:
        with pytest.raises(ValueError):
            await PipelineResultScorer(_Ragas(scores)).score(
                PipelineEvaluationResult((_query(),), {}), k=1
            )


def test_aggregate_rejects_empty_or_invalid_scored_rows():
    with pytest.raises(ValueError, match="empty"):
        aggregate_scored_results(())


def test_metrics_module_is_framework_and_persistence_independent():
    source = Path("app/airag/evaluation/rag_eval_metrics.py").read_text()
    forbidden = (
        "fastapi",
        "sqlalchemy",
        "app.services",
        "app.repositories",
        "app.models",
    )
    assert not any(name in source for name in forbidden)
