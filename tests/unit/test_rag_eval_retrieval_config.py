from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.rag_eval_schemas import (
    RagEvalPairProfileCreateRequest,
    RagEvalRetrievalConfig,
)
from app.services import rag_eval_service


def test_pair_request_requires_a_non_empty_retrieval_embedding_model():
    with pytest.raises(ValidationError):
        RagEvalPairProfileCreateRequest(
            name="baseline",
            rag_profile_id=1,
            chunking_profile_id=2,
            retrieval_config={"embedding_model": ""},
        )


def test_retrieval_config_validates_graph_build_values_when_supplied():
    with pytest.raises(ValidationError):
        RagEvalRetrievalConfig(
            embedding_model="text-embedding-3-small",
            graph_build={
                "llm_provider": "openai",
                "llm_model": "gpt-4o-mini",
                "max_paths_per_chunk": 0,
            },
        )


@pytest.mark.asyncio
async def test_create_graphrag_pair_requires_graph_build_configuration(monkeypatch):
    async def get_rag_profile(*_args):
        return SimpleNamespace(id=1, strategy="graphrag")

    async def get_chunking_profile(*_args):
        return SimpleNamespace(id=2)

    monkeypatch.setattr(rag_eval_service.rag_profiles_repo, "get_rag_profile_by_id", get_rag_profile)
    monkeypatch.setattr(rag_eval_service.chunking_profiles_repo, "get_chunking_profile_by_id", get_chunking_profile)

    with pytest.raises(ValueError, match="graph_build"):
        await rag_eval_service.create_rag_eval_pair_profile_srvc(
            RagEvalPairProfileCreateRequest(
                name="graph baseline",
                rag_profile_id=1,
                chunking_profile_id=2,
                retrieval_config={"embedding_model": "text-embedding-3-small"},
            ),
            object(),
            SimpleNamespace(id=3),
        )


@pytest.mark.asyncio
async def test_create_pair_rejects_rag_strategy_without_evaluation_adapter(monkeypatch):
    async def get_rag_profile(*_args):
        return SimpleNamespace(id=1, strategy="basic-rag")

    async def get_chunking_profile(*_args):
        return SimpleNamespace(id=2)

    monkeypatch.setattr(rag_eval_service.rag_profiles_repo, "get_rag_profile_by_id", get_rag_profile)
    monkeypatch.setattr(rag_eval_service.chunking_profiles_repo, "get_chunking_profile_by_id", get_chunking_profile)

    with pytest.raises(ValueError, match="Unsupported RAG evaluation strategy: basic-rag"):
        await rag_eval_service.create_rag_eval_pair_profile_srvc(
            RagEvalPairProfileCreateRequest(
                name="unsupported strategy",
                rag_profile_id=1,
                chunking_profile_id=2,
                retrieval_config={"embedding_model": "text-embedding-3-small"},
            ),
            object(),
            SimpleNamespace(id=3),
        )


@pytest.mark.asyncio
async def test_start_run_snapshots_pair_retrieval_configuration(monkeypatch):
    pair = SimpleNamespace(
        id=9,
        rag_profile_id=1,
        chunking_profile_id=2,
        retrieval_config={
            "embedding_model": "text-embedding-3-large",
            "graph_build": {
                "llm_provider": "openai",
                "llm_model": "gpt-4o-mini",
                "max_paths_per_chunk": 10,
            },
        },
    )
    captured = {}

    async def get_pair(*_args):
        return pair

    async def get_rag(*_args):
        return SimpleNamespace(id=1, name="graph", strategy="graphrag", config={})

    async def get_chunking(*_args):
        return SimpleNamespace(id=2, name="recursive", strategy="recursive", config={})

    async def create_run(run_in, _session):
        captured["snapshot"] = run_in.retrieval_config_snapshot
        captured["answer_snapshot"] = run_in.answer_generation_model_snapshot
        captured["judge_snapshot"] = run_in.evaluation_model_snapshot
        return SimpleNamespace(
            id=10,
            pair_profile_id=9,
            status="queued",
            stage="queued",
            cancel_requested=False,
            failure_detail=None,
            k=run_in.k,
            rag_profile_snapshot=run_in.rag_profile_snapshot,
            chunking_profile_snapshot=run_in.chunking_profile_snapshot,
            retrieval_config_snapshot=run_in.retrieval_config_snapshot,
            answer_generation_model_snapshot=run_in.answer_generation_model_snapshot,
            evaluation_model_snapshot=run_in.evaluation_model_snapshot,
            aggregate_hit_rate_at_k=None,
            aggregate_mrr_at_k=None,
            aggregate_ragas_metrics={},
            queued_at=__import__("datetime").datetime.now(),
            started_at=None,
            completed_at=None,
        )

    monkeypatch.setattr(rag_eval_service.rag_eval_repo, "get_rag_eval_pair_profile_by_id", get_pair)
    monkeypatch.setattr(rag_eval_service.rag_profiles_repo, "get_rag_profile_by_id", get_rag)
    monkeypatch.setattr(rag_eval_service.chunking_profiles_repo, "get_chunking_profile_by_id", get_chunking)
    monkeypatch.setattr(rag_eval_service.rag_eval_repo, "create_rag_eval_run", create_run)
    monkeypatch.setattr(
        rag_eval_service,
        "normalize_llm_selection",
        lambda provider, model: {"provider": provider, "model": model},
    )
    monkeypatch.setattr(
        rag_eval_service.asyncio,
        "create_task",
        lambda coroutine: coroutine.close(),
    )

    await rag_eval_service.start_rag_eval_run_srvc(
        9,
        rag_eval_service.RagEvalRunStartRequest(
            answer_llm_provider="ollama",
            answer_llm_model="qwen2.5:3b",
            judge_llm_provider="openai",
            judge_llm_model="gpt-4o-mini",
            judge_embedding_model="text-embedding-3-small",
        ),
        object(),
    )

    assert captured["snapshot"] == pair.retrieval_config
    assert captured["snapshot"] is not pair.retrieval_config
    assert captured["answer_snapshot"] == {
        "llm_provider": "ollama",
        "llm_model": "qwen2.5:3b",
        "temperature": 0,
        "prompt_version": "grounded_answer_v1",
    }
    assert captured["judge_snapshot"] == {
        "llm_provider": "openai",
        "llm_model": "gpt-4o-mini",
        "embedding_model": "text-embedding-3-small",
    }
