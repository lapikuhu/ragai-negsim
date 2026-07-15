"""Optional Ragas quality evaluation over completed deterministic eval runs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
)

from app.airag.embeddings.embeddings import choose_embedding_model
from app.airag.evaluation.eval_models import (
    EvalQueryResult,
    EvalRunResult,
    RagasQueryResult,
    RagasRunResult,
)
from app.airag.llm_models.llm_models import get_llm
from app.services.llm_models_service import normalize_llm_selection


DEFAULT_EVALUATION_EMBEDDING_MODEL = "text-embedding-3-small"
_METRIC_NAMES = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)


class RagasEvaluator:
    """Evaluate answer and context quality with the project model providers."""

    def __init__(
        self,
        llm: Any,
        embeddings: Any,
        metrics: Mapping[str, Any] | None = None,
    ) -> None:
        self.llm = llm
        self.embeddings = embeddings
        self.metrics = dict(metrics) if metrics is not None else {
            "faithfulness": Faithfulness(llm=llm),
            "answer_relevancy": AnswerRelevancy(llm=llm, embeddings=embeddings),
            "context_precision": ContextPrecision(llm=llm),
            "context_recall": ContextRecall(llm=llm),
        }
        if set(self.metrics) != set(_METRIC_NAMES):
            raise ValueError(f"Ragas metrics must be exactly: {', '.join(_METRIC_NAMES)}")

    @classmethod
    def from_model_selection(
        cls,
        provider: str | None = None,
        model: str | None = None,
        embedding_model: str | None = None,
    ) -> "RagasEvaluator":
        """
        Create an evaluator using project-supported model providers.
        Args:
            provider: The model provider to use for evaluation. If None, 
                the default provider is used.
            model: The model name to use for evaluation. If None, the 
                default model is used.
            embedding_model: The embedding model to use for evaluation. 
                If None, the default embedding model is used.
        Returns:
            An instance of RagasEvaluator.
        Raises:
            ValueError: If the selected evaluation LLM cannot be initialized.
        """
        selection = normalize_llm_selection(provider, model)
        project_llm = get_llm(
            provider=selection["provider"],
            model_name=selection["model"],
            temperature=0,
        )
        if project_llm is None:
            raise ValueError("Unable to initialize the selected evaluation LLM")
        project_embeddings, _ = choose_embedding_model(
            embedding_model or DEFAULT_EVALUATION_EMBEDDING_MODEL
        )
        return cls(
            llm=LangchainLLMWrapper(project_llm),
            embeddings=LangchainEmbeddingsWrapper(project_embeddings),
        )

    @staticmethod
    def _metric_payload(metric_name: str, result: EvalQueryResult) -> dict[str, Any]:
        """
        Generate the payload for a specific metric.

        Args:
            metric_name: The name of the metric.
            result: The evaluation query result.

        Returns:
            A dictionary containing the payload for the metric.
        Raises:
            ValueError: If the evaluation result has no generated answer."""
        if result.answer is None or not result.answer.strip():
            raise ValueError(f"Evaluation {result.evaluation_id} has no generated answer")
        payload = {
            "user_input": result.query,
            "response": result.answer,
            "retrieved_contexts": list(result.retrieved_contexts),
        }
        if metric_name in {"context_precision", "context_recall"}:
            payload["reference"] = result.reference
        if metric_name == "answer_relevancy":
            payload.pop("retrieved_contexts")
        return payload

    async def _score_metric(self, metric_name: str, result: EvalQueryResult) -> float:
        """
        Score a specific metric for a given evaluation query result.
        Args:
            metric_name: The name of the metric to score.
            result: The evaluation query result.

        Returns:
            The score for the specified metric.

        Raises:
            RuntimeError: If the metric scoring fails after retrying.
        """
        metric = self.metrics[metric_name]
        payload = self._metric_payload(metric_name, result)
        for attempt in range(2):
            try:
                scored = await metric.ascore(**payload)
                return float(scored.value)
            except Exception as exc:
                if attempt == 1:
                    raise RuntimeError(
                        f"Ragas metric {metric_name} failed for evaluation {result.evaluation_id}"
                    ) from exc
        raise AssertionError("unreachable")

    async def evaluate(self, eval_run: EvalRunResult) -> RagasRunResult:
        """
        Score every query in an ``EvalRunResult`` and aggregate each metric.
        Args:
            eval_run: The evaluation run result containing all query results.
        Returns:
            A ``RagasRunResult`` containing the scored query results and 
            aggregated metric means.
        Raises:
            ValueError: If the evaluation run result is empty.
        """
        if not eval_run.results:
            raise ValueError("Cannot run Ragas evaluation for an empty EvalRunResult")
        query_results: list[RagasQueryResult] = []
        for result in eval_run.results:
            scores = {
                metric_name: await self._score_metric(metric_name, result)
                for metric_name in _METRIC_NAMES
            }
            query_results.append(
                RagasQueryResult(evaluation_id=result.evaluation_id, metric_scores=scores)
            )
        return RagasRunResult(
            results=tuple(query_results),
            metric_means={
                metric_name: sum(row.metric_scores[metric_name] for row in query_results)
                / len(query_results)
                for metric_name in _METRIC_NAMES
            },
        )
