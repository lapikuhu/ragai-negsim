import pytest

from app import main
from app.services import (
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

    async with main.lifespan(main.app):
        assert recovered == [
            "seed",
            "indexing",
            "knowledge-graphs",
            "rag-eval-start",
        ]

    assert recovered[-1] == "rag-eval-stop"
