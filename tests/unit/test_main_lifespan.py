import pytest

from app import main
from app.services import (
    corpus_bm25_build_coordinator,
    corpus_bm25_build_jobs_service,
    full_corpus_index_pipe_job,
    knowledge_graph_builds_service,
    rag_eval_service,
)


@pytest.mark.asyncio
async def test_lifespan_recovers_indexing_and_knowledge_graph_jobs(monkeypatch):
    recovered = []

    async def fake_startup_seed():
        recovered.append("seed")

    async def fake_recover_indexing():
        recovered.append("indexing")

    async def fake_recover_knowledge_graphs():
        recovered.append("knowledge-graphs")

    async def fake_start_rag_evaluations():
        recovered.append("rag-eval-start")

    async def fake_stop_rag_evaluations():
        recovered.append("rag-eval-stop")

    async def fake_recover_bm25(_session):
        recovered.append("bm25-recovery")

    async def fake_start_bm25():
        recovered.append("bm25-start")

    async def fake_stop_bm25():
        recovered.append("bm25-stop")

    monkeypatch.setattr(main, "startup_seed", fake_startup_seed)
    monkeypatch.setattr(
        full_corpus_index_pipe_job,
        "fail_interrupted_full_corpus_index_pipe_jobs_srvc",
        fake_recover_indexing,
    )
    monkeypatch.setattr(
        knowledge_graph_builds_service,
        "fail_interrupted_knowledge_graph_builds_srvc",
        fake_recover_knowledge_graphs,
    )
    monkeypatch.setattr(
        rag_eval_service,
        "startup_rag_eval_coordinator_srvc",
        fake_start_rag_evaluations,
    )
    monkeypatch.setattr(
        rag_eval_service,
        "shutdown_rag_eval_coordinator_srvc",
        fake_stop_rag_evaluations,
    )
    monkeypatch.setattr(
        corpus_bm25_build_jobs_service,
        "recover_interrupted_corpus_bm25_build_jobs_srvc",
        fake_recover_bm25,
    )
    monkeypatch.setattr(
        corpus_bm25_build_coordinator,
        "startup_corpus_bm25_build_coordinator_srvc",
        fake_start_bm25,
    )
    monkeypatch.setattr(
        corpus_bm25_build_coordinator,
        "shutdown_corpus_bm25_build_coordinator_srvc",
        fake_stop_bm25,
    )

    async with main.lifespan(main.app):
        assert recovered == [
            "seed",
            "indexing",
            "knowledge-graphs",
            "bm25-recovery",
            "bm25-start",
            "rag-eval-start",
        ]

    assert recovered[-2:] == ["bm25-stop", "rag-eval-stop"]
