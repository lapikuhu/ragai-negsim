from types import SimpleNamespace

import pytest

from app.airag.evaluation.eval_models import EvalQueryResult, EvalRunResult


def _run(*, contexts=("Evidence one.",), answer=None):
    return EvalRunResult(
        k=2,
        results=(
            EvalQueryResult(
                evaluation_id="sample:1",
                query="What happened?",
                answer=answer,
                reference="Reference.",
                retrieved_contexts=contexts,
                retrieved_evaluation_ids=((),),
                first_relevant_rank=1,
                hit_at_k=True,
                reciprocal_rank_at_k=1.0,
            ),
        ),
        hit_rate_at_k=1.0,
        mrr_at_k=1.0,
    )


@pytest.mark.asyncio
async def test_generator_replaces_retrieval_context_with_grounded_answer(monkeypatch):
    from app.airag.evaluation import answer_generation

    captured = {}
    monkeypatch.setattr(
        answer_generation,
        "normalize_llm_selection",
        lambda provider, model: {"provider": provider, "model": model},
    )
    def fake_get_llm(**kwargs):
        captured["llm"] = kwargs
        return object()

    def fake_invoke(_llm, prompt, _config=None):
        captured["prompt"] = prompt
        return SimpleNamespace(content="A grounded answer.")

    monkeypatch.setattr(answer_generation, "get_llm", fake_get_llm)
    monkeypatch.setattr(answer_generation, "guarded_invoke_with_config", fake_invoke)

    result = await answer_generation.generate_grounded_answers(
        _run(), provider="openai", model="gpt-4o-mini"
    )

    assert result.results[0].answer == "A grounded answer."
    assert "What happened?" in captured["prompt"]
    assert "Evidence one." in captured["prompt"]
    assert captured["llm"]["temperature"] == 0


@pytest.mark.asyncio
async def test_generator_uses_fixed_abstention_without_context_or_llm(monkeypatch):
    from app.airag.evaluation import answer_generation

    monkeypatch.setattr(answer_generation, "get_llm", lambda **_kwargs: pytest.fail("LLM must not be created"))

    result = await answer_generation.generate_grounded_answers(
        _run(contexts=()), provider="openai", model="gpt-4o-mini"
    )

    assert result.results[0].answer == answer_generation.NO_RETRIEVED_EVIDENCE_ANSWER


@pytest.mark.asyncio
async def test_generator_checks_cancellation_between_answers(monkeypatch):
    from app.airag.evaluation import answer_generation

    second = EvalQueryResult(
        evaluation_id="sample:2",
        query="What next?",
        answer=None,
        reference="Reference.",
        retrieved_contexts=("Evidence two.",),
        retrieved_evaluation_ids=((),),
        first_relevant_rank=1,
        hit_at_k=True,
        reciprocal_rank_at_k=1.0,
    )
    run = _run()
    run = EvalRunResult(k=run.k, results=(run.results[0], second), hit_rate_at_k=1.0, mrr_at_k=1.0)
    calls = []
    monkeypatch.setattr(answer_generation, "normalize_llm_selection", lambda provider, model: {"provider": provider, "model": model})
    monkeypatch.setattr(answer_generation, "get_llm", lambda **_kwargs: object())
    monkeypatch.setattr(answer_generation, "guarded_invoke_with_config", lambda *_args: SimpleNamespace(content="answer"))

    async def cancelled():
        calls.append(None)
        return len(calls) > 1

    with pytest.raises(answer_generation.RagEvalAnswerGenerationCancelled):
        await answer_generation.generate_grounded_answers(
            run, provider="openai", model="gpt-4o-mini", should_cancel=cancelled
        )
