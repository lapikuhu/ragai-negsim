import pytest

from app import main
from app.services import (
    indexing_jobs_service,
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

    async def fake_recover_rag_evaluations():
        recovered.append("rag-eval")

    monkeypatch.setattr(main, "startup_seed", fake_startup_seed)
    monkeypatch.setattr(
        indexing_jobs_service,
        "fail_interrupted_indexing_jobs_srvc",
        fake_recover_indexing,
    )
    monkeypatch.setattr(
        knowledge_graph_builds_service,
        "fail_interrupted_knowledge_graph_builds_srvc",
        fake_recover_knowledge_graphs,
    )
    monkeypatch.setattr(
        rag_eval_service,
        "fail_interrupted_rag_eval_runs_srvc",
        fake_recover_rag_evaluations,
    )

    async with main.lifespan(main.app):
        assert recovered == ["seed", "indexing", "knowledge-graphs", "rag-eval"]
