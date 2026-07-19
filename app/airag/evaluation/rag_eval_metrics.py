"""Framework-independent scoring for completed full-pipeline evaluations."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.airag.evaluation.rag_eval_engine import (
    CancellationCallback,
    PipelineEvaluationResult,
    RankedEvaluationDocument,
    check_cancellation,
)

# TODO: Move to a config file
RAGAS_METRIC_NAMES = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "answer_correctness",
)


@dataclass(frozen=True)
class ScoredPipelineQueryResult:
    evaluation_id: str
    category: str
    answerable: bool
    query: str
    reference_answer: str
    answer: str
    ranked_documents: tuple[RankedEvaluationDocument, ...]
    first_relevant_rank: int | None
    hit_at_k: bool | None
    mrr_at_k: float | None
    successful_abstention: bool | None
    false_positive_context: bool | None
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    answer_correctness: float


@dataclass(frozen=True)
class ScoredPipelineEvaluationResult:
    results: tuple[ScoredPipelineQueryResult, ...]
    overall_metrics: Mapping[str, float]
    category_metrics: Mapping[str, Mapping[str, float]]
    resolved_pipeline_snapshot: Mapping[str, Any]


def aggregate_scored_results(
    results: Sequence[ScoredPipelineQueryResult],
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """
    Return means and equal-weight, higher-is-better overall scores.
    Args:
        results: A sequence of scored pipeline query results.
    Returns:
        A tuple containing:
            - A dictionary of overall mean scores for each metric.
            - A dictionary mapping each category to its mean scores for 
                each metric.
    Raises:
        ValueError: If the results sequence is empty or if any metric is 
        invalid.
    """
    if not results:
        raise ValueError("Cannot aggregate an empty scored result set")

    def aggregate(rows: Sequence[ScoredPipelineQueryResult]) -> dict[str, float]:
        values: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            for name in RAGAS_METRIC_NAMES:
                values[name].append(_validated_score(name, getattr(row, name)))
            if row.hit_at_k is not None:
                values["hit_at_k"].append(float(row.hit_at_k))
            if row.mrr_at_k is not None:
                values["mrr_at_k"].append(
                    _validated_score("mrr_at_k", row.mrr_at_k)
                )
            if row.successful_abstention is not None:
                values["successful_abstention"].append(
                    float(row.successful_abstention)
                )
            if row.false_positive_context is not None:
                values["false_positive_context_rate"].append(
                    float(row.false_positive_context)
                )

        means = {name: sum(items) / len(items) for name, items in values.items()}
        quality_components = [
            value
            for name, value in means.items()
            if name != "false_positive_context_rate"
        ]
        if "false_positive_context_rate" in means:
            quality_components.append(1.0 - means["false_positive_context_rate"])
        if not quality_components:
            raise ValueError("No applicable metric components to aggregate")
        means["overall_score"] = sum(quality_components) / len(quality_components)
        return means

    by_category: dict[str, list[ScoredPipelineQueryResult]] = defaultdict(list)
    for row in results:
        by_category[row.category].append(row)
    return aggregate(results), {
        category: aggregate(rows) for category, rows in by_category.items()
    }


def _validated_score(name: str, value: Any) -> float:
    """
    Validate that a score is numeric and within the range [0, 1].
    Args:
        name: The name of the metric.
        value: The value of the metric.
    Returns:
        The validated score as a float.
    Raises:
        ValueError: If the score is not numeric or not in the range [0, 1].
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Metric {name} must be numeric")
    score = float(value)
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError(f"Metric {name} must be finite and in [0, 1]")
    return score


def _validated_ragas_scores(scores: Mapping[str, Any]) -> dict[str, float]:
    if set(scores) != set(RAGAS_METRIC_NAMES):
        """
        Validate that the Ragas scores contain exactly the required metrics.
        Raises:
            ValueError: If the scores do not contain exactly the required metrics.
        """
        raise ValueError(
            "Ragas scores must contain exactly: " + ", ".join(RAGAS_METRIC_NAMES)
        )
    return {
        name: _validated_score(name, scores[name]) for name in RAGAS_METRIC_NAMES
    }


class PipelineResultScorer:
    def __init__(self, ragas_evaluator: Any) -> None:
        self._ragas_evaluator = ragas_evaluator

    async def score(
        self,
        evaluation: PipelineEvaluationResult,
        *,
        k: int,
        should_cancel: CancellationCallback | None = None,
    ) -> ScoredPipelineEvaluationResult:
        """
        Score a pipeline evaluation result.
        Args:
            evaluation: The pipeline evaluation result to score.
            k: The cutoff rank for retrieval metrics.
            should_cancel: Optional callback to check for cancellation.
        Returns:
            A ScoredPipelineEvaluationResult containing the scored query 
            results and aggregated metrics.

        Raises:
            ValueError: If the evaluation result is empty or if k is not 
            a positive integer.
        """
        if not evaluation.results:
            raise ValueError("Cannot score an empty pipeline evaluation result")
        if isinstance(k, bool) or not isinstance(k, int) or k < 1:
            raise ValueError("Metric k must be a positive integer")

        scored_rows: list[ScoredPipelineQueryResult] = []
        for result in evaluation.results:
            await check_cancellation(should_cancel)
            ragas_scores = _validated_ragas_scores(
                await self._ragas_evaluator.score_query(
                    result,
                    should_cancel=should_cancel,
                )
            )
            await check_cancellation(should_cancel)

            if result.answerable:
                first_relevant_rank = next(
                    (
                        rank
                        for rank, document in enumerate(
                            result.ranked_documents[:k], start=1
                        )
                        if result.evaluation_id in document.evaluation_ids
                    ),
                    None,
                )
                hit_at_k: bool | None = first_relevant_rank is not None
                mrr_at_k: float | None = (
                    1.0 / first_relevant_rank
                    if first_relevant_rank is not None
                    else 0.0
                )
                successful_abstention = None
                false_positive_context = None
                # Future multi-hop metrics: required-evidence coverage@k and
                # all-evidence-hit@k. Current behavior intentionally preserves
                # first-relevant Hit@k/MRR@k semantics.
            else:
                first_relevant_rank = None
                hit_at_k = None
                mrr_at_k = None
                # Deterministic definition: the canonical final response
                # successfully abstains iff it uses zero final answer-context
                # documents. Any final ranked document is false-positive context.
                false_positive_context = bool(result.ranked_documents)
                successful_abstention = not false_positive_context

            scored_rows.append(
                ScoredPipelineQueryResult(
                    evaluation_id=result.evaluation_id,
                    category=result.category,
                    answerable=result.answerable,
                    query=result.query,
                    reference_answer=result.reference_answer,
                    answer=result.answer,
                    ranked_documents=result.ranked_documents,
                    first_relevant_rank=first_relevant_rank,
                    hit_at_k=hit_at_k,
                    mrr_at_k=mrr_at_k,
                    successful_abstention=successful_abstention,
                    false_positive_context=false_positive_context,
                    **ragas_scores,
                )
            )

        overall, categories = aggregate_scored_results(scored_rows)
        return ScoredPipelineEvaluationResult(
            results=tuple(scored_rows),
            overall_metrics=overall,
            category_metrics=categories,
            resolved_pipeline_snapshot=evaluation.resolved_pipeline_snapshot,
        )
