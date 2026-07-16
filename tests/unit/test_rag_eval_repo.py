from types import SimpleNamespace

import pytest

from app.repositories import rag_eval_repo
from app.schemas.rag_eval_schemas import RagEvalPairProfileCreate, RagEvalRunCreate


def test_rag_eval_models_capture_audited_pair_and_run_snapshots():
    from app.models.rag_eval import RagEvalPairProfile, RagEvalQueryResult, RagEvalRun

    pair = RagEvalPairProfile(
        name="baseline",
        rag_profile_id=1,
        chunking_profile_id=2,
        created_by_user_id=3,
    )
    run = RagEvalRun(
        pair_profile_id=1,
        k=5,
        rag_profile_snapshot={"strategy": "crag"},
        chunking_profile_snapshot={"strategy": "recursive"},
        answer_generation_model_snapshot={"llm_provider": "openai", "llm_model": "gpt-4.1"},
        evaluation_model_snapshot={"provider": "openai", "model": "gpt-4.1"},
    )
    result = RagEvalQueryResult(
        run_id=1,
        evaluation_id="case-1",
        query="What is BATNA?",
        reference_answer="Best alternative.",
        retrieved_contexts=["context"],
        retrieved_evaluation_ids=["case-1"],
    )

    assert pair.last_edit_by_user_id is None
    assert run.status == "queued"
    assert run.aggregate_ragas_metrics == {}
    assert run.answer_generation_model_snapshot["llm_model"] == "gpt-4.1"
    assert RagEvalRun.__table__.c.answer_generation_model_snapshot.nullable is False
    assert result.hit_at_k is False


def test_rag_eval_run_table_has_active_pair_index_and_status_constraint():
    from sqlalchemy import CheckConstraint, Index

    from app.models.rag_eval import RagEvalRun

    constraints = {
        constraint.name: constraint
        for constraint in RagEvalRun.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    indexes = {
        index.name: index
        for index in RagEvalRun.__table__.indexes
        if isinstance(index, Index)
    }

    assert str(constraints["ck_rag_eval_run_valid_status"].sqltext) == (
        "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')"
    )
    active_run_index = indexes["uq_rag_eval_run_active_pair"]
    assert active_run_index.unique is True
    assert [column.name for column in active_run_index.columns] == ["pair_profile_id"]
    assert str(active_run_index.dialect_options["postgresql"]["where"]) == (
        "status IN ('queued', 'running')"
    )


@pytest.mark.asyncio
async def test_create_pair_allows_shared_rag_chunk_combination_when_names_differ(monkeypatch):
    async def fake_get_pair_by_name(name, session):
        return None

    monkeypatch.setattr(
        rag_eval_repo,
        "get_rag_eval_pair_profile_by_name",
        fake_get_pair_by_name,
    )

    async def fake_commit_and_refresh(_session, profile):
        return profile

    monkeypatch.setattr(rag_eval_repo, "commit_and_refresh", fake_commit_and_refresh)

    profile = await rag_eval_repo.create_rag_eval_pair_profile(
        RagEvalPairProfileCreate(
            name="baseline",
            rag_profile_id=1,
            chunking_profile_id=2,
            retrieval_config={"embedding_model": "text-embedding-3-small"},
            created_by_user_id=3,
        ),
        object(),
    )

    assert profile.rag_profile_id == 1
    assert profile.chunking_profile_id == 2


@pytest.mark.asyncio
async def test_pair_update_and_delete_are_rejected_after_run_exists(monkeypatch):
    pair = SimpleNamespace(id=4, name="baseline")

    async def fake_pair_has_runs(pair_id, session):
        return True

    monkeypatch.setattr(rag_eval_repo, "rag_eval_pair_profile_has_runs", fake_pair_has_runs)

    with pytest.raises(ValueError, match="has evaluation runs"):
        await rag_eval_repo.ensure_rag_eval_pair_profile_mutable(pair, object())


@pytest.mark.asyncio
async def test_create_run_rejects_another_active_run_for_pair(monkeypatch):
    async def fake_get_active_run(pair_profile_id, session):
        return SimpleNamespace(id=9, status="running")

    monkeypatch.setattr(rag_eval_repo, "get_active_rag_eval_run", fake_get_active_run)

    with pytest.raises(ValueError, match="active evaluation run"):
        await rag_eval_repo.create_rag_eval_run(
            RagEvalRunCreate(
                pair_profile_id=1,
                k=5,
                rag_profile_snapshot={},
                chunking_profile_snapshot={},
                evaluation_model_snapshot={},
            ),
            object(),
        )


@pytest.mark.asyncio
async def test_run_state_helpers_persist_metrics_and_terminal_status(monkeypatch):
    run = SimpleNamespace(
        status="running",
        stage="evaluating",
        aggregate_hit_rate_at_k=None,
        aggregate_mrr_at_k=None,
        aggregate_ragas_metrics={},
        failure_detail=None,
        completed_at=None,
        cancel_requested=True,
    )

    async def fake_commit_and_refresh(session, instance):
        return instance

    monkeypatch.setattr(rag_eval_repo, "commit_and_refresh", fake_commit_and_refresh)

    completed = await rag_eval_repo.mark_rag_eval_run_completed(
        run,
        object(),
        hit_rate_at_k=0.8,
        mrr_at_k=0.7,
        ragas_metrics={"faithfulness": 0.9},
    )

    assert completed.status == "completed"
    assert completed.stage == "finished"
    assert completed.aggregate_hit_rate_at_k == 0.8
    assert completed.aggregate_mrr_at_k == 0.7
    assert completed.aggregate_ragas_metrics == {"faithfulness": 0.9}
    assert completed.cancel_requested is False


@pytest.mark.asyncio
async def test_run_state_helpers_reject_invalid_status(monkeypatch):
    run = SimpleNamespace(status="queued")

    async def fail_if_committed(*args, **kwargs):
        raise AssertionError("invalid status must not be committed")

    monkeypatch.setattr(rag_eval_repo, "commit_and_refresh", fail_if_committed)

    with pytest.raises(ValueError, match="Invalid RAG evaluation run status transition"):
        await rag_eval_repo.update_rag_eval_run(run, object(), status="unknown")
