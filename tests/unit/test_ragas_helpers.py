from __future__ import annotations

import pytest
from ragas.dataset_schema import SingleTurnSample

from app.airag.evaluation.eval_models import EvalQueryResult, EvalRunResult
from app.airag.evaluation.rag_eval_engine import (
    PipelineQueryResult,
    RagEvaluationCancelled,
    RankedEvaluationDocument,
)
from app.airag.evaluation.ragas_helpers import RagasEvaluator


class FakeMetric:
    def __init__(self, value: float, failures: int = 0):
        self.value = value
        self.failures = failures
        self.calls: list[dict] = []

    async def single_turn_ascore(self, sample: SingleTurnSample) -> float:
        self.calls.append(sample.model_dump(exclude_none=True))
        if self.failures:
            self.failures -= 1
            raise RuntimeError("temporary failure")
        return self.value


class ContractMetric:
    """Test double matching the locked RAGAS 0.3.1 metric contract."""

    def __init__(self, value: float):
        self.value = value
        self.calls: list[SingleTurnSample] = []

    async def single_turn_ascore(self, sample: SingleTurnSample) -> float:
        self.calls.append(sample)
        return self.value


class InitializableMetric(FakeMetric):
    def __init__(self, value: float = 0.0):
        super().__init__(value)
        self.init_calls: list[object] = []

    def init(self, run_config: object) -> None:
        self.init_calls.append(run_config)


class ConfigurableWrapper:
    def __init__(self, value: object):
        self.value = value
        self.run_configs: list[object] = []

    def set_run_config(self, run_config: object) -> None:
        self.run_configs.append(run_config)


def _eval_run(answer: str | None = "Generated answer") -> EvalRunResult:
    return EvalRunResult(
        k=2,
        results=(
            EvalQueryResult(
                evaluation_id="sample:1",
                query="What is it?",
                answer=answer,
                reference="Reference answer",
                retrieved_contexts=("First context", "Second context"),
                retrieved_evaluation_ids=((), ()),
                first_relevant_rank=1,
                hit_at_k=True,
                reciprocal_rank_at_k=1.0,
            ),
        ),
        hit_rate_at_k=1.0,
        mrr_at_k=1.0,
    )


def test_evaluator_initializes_default_metrics_with_one_shared_run_config(monkeypatch):
    import app.airag.evaluation.ragas_helpers as helpers

    run_config = object()
    created_metrics = {
        "faithfulness": InitializableMetric(),
        "answer_relevancy": InitializableMetric(),
        "context_precision": InitializableMetric(),
        "context_recall": InitializableMetric(),
        "answer_correctness": InitializableMetric(),
    }
    constructors = {
        "Faithfulness": "faithfulness",
        "AnswerRelevancy": "answer_relevancy",
        "ContextPrecision": "context_precision",
        "ContextRecall": "context_recall",
        "AnswerCorrectness": "answer_correctness",
    }
    for constructor_name, metric_name in constructors.items():
        monkeypatch.setattr(
            helpers,
            constructor_name,
            lambda *args, _metric_name=metric_name, **kwargs: created_metrics[_metric_name],
        )
    monkeypatch.setattr(helpers, "RunConfig", lambda: run_config, raising=False)

    evaluator = RagasEvaluator(llm=object(), embeddings=object())

    assert evaluator.metrics == created_metrics
    assert all(metric.init_calls == [run_config] for metric in created_metrics.values())


def test_evaluator_leaves_injected_metrics_uninitialized():
    metrics = {
        "faithfulness": InitializableMetric(),
        "answer_relevancy": InitializableMetric(),
        "context_precision": InitializableMetric(),
        "context_recall": InitializableMetric(),
        "answer_correctness": InitializableMetric(),
    }

    evaluator = RagasEvaluator(llm=object(), embeddings=object(), metrics=metrics)

    assert evaluator.metrics == metrics
    assert all(metric.init_calls == [] for metric in metrics.values())


@pytest.mark.asyncio
async def test_evaluator_uses_ragas_031_single_turn_scoring_contract():
    metrics = {
        "faithfulness": ContractMetric(0.1),
        "answer_relevancy": ContractMetric(0.2),
        "context_precision": ContractMetric(0.3),
        "context_recall": ContractMetric(0.4),
        "answer_correctness": ContractMetric(0.5),
    }

    result = await RagasEvaluator(
        llm=object(), embeddings=object(), metrics=metrics
    ).evaluate(_eval_run())

    assert result.metric_means["faithfulness"] == 0.1
    sample = metrics["faithfulness"].calls[0]
    assert isinstance(sample, SingleTurnSample)
    assert sample.user_input == "What is it?"
    assert sample.response == "Generated answer"
    assert sample.retrieved_contexts == ["First context", "Second context"]


@pytest.mark.asyncio
async def test_evaluator_scores_eval_run_and_aggregates_metric_means():
    metrics = {
        "faithfulness": FakeMetric(0.1),
        "answer_relevancy": FakeMetric(0.2),
        "context_precision": FakeMetric(0.3),
        "context_recall": FakeMetric(0.4),
        "answer_correctness": FakeMetric(0.5),
    }
    evaluator = RagasEvaluator(llm=object(), embeddings=object(), metrics=metrics)

    result = await evaluator.evaluate(_eval_run())

    assert result.metric_means == {
        "faithfulness": 0.1,
        "answer_relevancy": 0.2,
        "context_precision": 0.3,
        "context_recall": 0.4,
        "answer_correctness": 0.5,
    }
    assert metrics["faithfulness"].calls == [{
        "user_input": "What is it?",
        "response": "Generated answer",
        "retrieved_contexts": ["First context", "Second context"],
    }]
    assert metrics["context_precision"].calls[0]["reference"] == "Reference answer"
    assert metrics["answer_correctness"].calls == [{
        "user_input": "What is it?",
        "response": "Generated answer",
        "reference": "Reference answer",
    }]
    assert metrics["answer_relevancy"].calls == [{
        "user_input": "What is it?",
        "response": "Generated answer",
    }]
    assert metrics["context_recall"].calls == [{
        "user_input": "What is it?",
        "response": "Generated answer",
        "retrieved_contexts": ["First context", "Second context"],
        "reference": "Reference answer",
    }]


@pytest.mark.asyncio
async def test_pipeline_query_payloads_use_actual_answer_final_contexts_and_reference():
    metrics = {
        "faithfulness": FakeMetric(0.1),
        "answer_relevancy": FakeMetric(0.2),
        "context_precision": FakeMetric(0.3),
        "context_recall": FakeMetric(0.4),
        "answer_correctness": FakeMetric(0.5),
    }
    query = PipelineQueryResult(
        evaluation_id="pipeline-1",
        category="direct_retrieval",
        answerable=True,
        query="Pipeline query",
        reference_answer="Pipeline reference",
        answer="Graph answer",
        contexts=("Final context",),
        ranked_documents=(
            RankedEvaluationDocument(
                content="Final context",
                rank=1,
                metadata={},
                evaluation_ids=("pipeline-1",),
            ),
        ),
    )

    scores = await RagasEvaluator(
        llm=object(), embeddings=object(), metrics=metrics
    ).score_query(query)

    assert scores == {
        "faithfulness": 0.1,
        "answer_relevancy": 0.2,
        "context_precision": 0.3,
        "context_recall": 0.4,
        "answer_correctness": 0.5,
    }
    assert metrics["faithfulness"].calls == [{
        "user_input": "Pipeline query",
        "response": "Graph answer",
        "retrieved_contexts": ["Final context"],
    }]


@pytest.mark.asyncio
async def test_cancellation_after_metric_provider_call_stops_before_next_metric():
    metrics = {
        "faithfulness": FakeMetric(0.1),
        "answer_relevancy": FakeMetric(0.2),
        "context_precision": FakeMetric(0.3),
        "context_recall": FakeMetric(0.4),
        "answer_correctness": FakeMetric(0.5),
    }

    async def should_cancel():
        return bool(metrics["faithfulness"].calls)

    with pytest.raises(RagEvaluationCancelled):
        await RagasEvaluator(
            llm=object(), embeddings=object(), metrics=metrics
        ).evaluate(_eval_run(), should_cancel=should_cancel)

    assert len(metrics["faithfulness"].calls) == 1
    assert metrics["answer_relevancy"].calls == []


def test_evaluator_factory_accepts_normalized_configuration(monkeypatch):
    calls = []
    monkeypatch.setattr(
        RagasEvaluator,
        "from_model_selection",
        lambda provider, model, embedding_model: calls.append(
            (provider, model, embedding_model)
        )
        or "evaluator",
    )

    result = RagasEvaluator.from_normalized_configuration(
        {
            "metrics": {
                "k": 3,
                "ragas_judge": {"provider": "openai", "model": "gpt-4o-mini"},
                "judge_embedding_model": "text-embedding-3-small",
            }
        }
    )

    assert result == "evaluator"
    assert calls == [
        ("openai", "gpt-4o-mini", "text-embedding-3-small")
    ]


@pytest.mark.asyncio
async def test_evaluator_retries_a_failed_metric_once():
    retrying_metric = FakeMetric(0.1, failures=1)
    evaluator = RagasEvaluator(
        llm=object(),
        embeddings=object(),
        metrics={
            "faithfulness": retrying_metric,
            "answer_relevancy": FakeMetric(0.2),
            "context_precision": FakeMetric(0.3),
            "context_recall": FakeMetric(0.4),
            "answer_correctness": FakeMetric(0.5),
        },
    )

    await evaluator.evaluate(_eval_run())

    assert len(retrying_metric.calls) == 2


@pytest.mark.asyncio
async def test_evaluator_raises_after_retry_with_metric_and_evaluation_id():
    evaluator = RagasEvaluator(
        llm=object(),
        embeddings=object(),
        metrics={
            "faithfulness": FakeMetric(0.1, failures=2),
            "answer_relevancy": FakeMetric(0.2),
            "context_precision": FakeMetric(0.3),
            "context_recall": FakeMetric(0.4),
            "answer_correctness": FakeMetric(0.5),
        },
    )

    with pytest.raises(RuntimeError, match="faithfulness.*sample:1"):
        await evaluator.evaluate(_eval_run())


@pytest.mark.asyncio
async def test_evaluator_rejects_missing_generated_answer_before_scoring():
    metric = FakeMetric(0.1)
    evaluator = RagasEvaluator(
        llm=object(),
        embeddings=object(),
        metrics={
            "faithfulness": metric,
            "answer_relevancy": FakeMetric(0.2),
            "context_precision": FakeMetric(0.3),
            "context_recall": FakeMetric(0.4),
            "answer_correctness": FakeMetric(0.5),
        },
    )

    with pytest.raises(ValueError, match="sample:1.*generated answer"):
        await evaluator.evaluate(_eval_run(answer=None))
    assert metric.calls == []


def test_evaluator_factory_uses_project_model_and_embedding_factories(monkeypatch):
    import app.airag.evaluation.ragas_helpers as helpers

    llm_calls = []

    monkeypatch.setattr(
        helpers,
        "normalize_llm_selection",
        lambda provider, model: {"provider": "ollama", "model": "qwen"},
    )
    monkeypatch.setattr(
        helpers,
        "get_llm",
        lambda **kwargs: llm_calls.append(kwargs) or "project-llm",
    )
    monkeypatch.setattr(helpers, "choose_embedding_model", lambda model: ("project-embeddings", {}))
    monkeypatch.setattr(helpers, "LangchainLLMWrapper", ConfigurableWrapper)
    monkeypatch.setattr(
        helpers, "LangchainEmbeddingsWrapper", ConfigurableWrapper
    )

    evaluator = RagasEvaluator.from_model_selection(
        provider="ollama", model="qwen", embedding_model="mini-l6-v2"
    )

    assert evaluator.llm.value == "project-llm"
    assert evaluator.embeddings.value == "project-embeddings"
    assert llm_calls == [
        {
            "provider": "ollama",
            "model_name": "qwen",
            "temperature": 0,
            "do_not_bind_runnable_config": True,
        }
    ]
    assert set(evaluator.metrics) == {
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "answer_correctness",
    }
    assert evaluator.metrics["answer_correctness"].answer_similarity is not None
