from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services import knowledge_graph_builds_service


@pytest.mark.asyncio
async def test_queue_graph_build_snapshots_exact_indexed_chunks(
    monkeypatch,
    recording_async_session_factory,
):
    session = recording_async_session_factory()
    graph = SimpleNamespace(
        id=5,
        corpus_index_id=9,
        build_config={"extractors": ["schema"]},
        locked_at=None,
        status="created",
    )
    chunks = [SimpleNamespace(id=11), SimpleNamespace(id=12)]
    captured = {}

    async def fake_get_graph(graph_id, session):
        return graph

    async def fake_get_index(index_id, session):
        return SimpleNamespace(id=index_id, status="built")

    async def fake_list_chunks(index_id, session):
        return chunks

    async def fake_create_job(job_in, session):
        captured["job"] = job_in
        return SimpleNamespace(
            id=44,
            processed_chunks=0,
            cancel_requested=False,
            failure_detail=None,
            queued_at=datetime.now(timezone.utc),
            started_at=None,
            completed_at=None,
            **job_in.model_dump(),
        )

    monkeypatch.setattr(
        knowledge_graph_builds_service.knowledge_graph_indices_repo,
        "get_knowledge_graph_index_by_id",
        fake_get_graph,
    )
    monkeypatch.setattr(
        knowledge_graph_builds_service.corpus_indices_repo,
        "get_corpus_index_by_id",
        fake_get_index,
    )
    monkeypatch.setattr(
        knowledge_graph_builds_service.document_chunks_repo,
        "list_document_chunks_for_corpus_index",
        fake_list_chunks,
    )
    monkeypatch.setattr(
        knowledge_graph_builds_service.knowledge_graph_build_jobs_repo,
        "create_knowledge_graph_build_job",
        fake_create_job,
    )

    result = await knowledge_graph_builds_service.queue_knowledge_graph_build_srvc(
        5,
        session,
    )

    assert result.id == 44
    assert captured["job"].chunk_ids_snapshot == [11, 12]
    assert captured["job"].total_chunks == 2
    assert captured["job"].candidate_generation


@pytest.mark.asyncio
async def test_queue_graph_rebuild_rejects_locked_graph(
    monkeypatch,
    recording_async_session_factory,
):
    session = recording_async_session_factory()
    graph = SimpleNamespace(
        id=5,
        corpus_index_id=9,
        build_config={"extractors": ["schema"]},
        locked_at=object(),
        status="built",
    )

    async def fake_get_graph(graph_id, session):
        return graph

    monkeypatch.setattr(
        knowledge_graph_builds_service.knowledge_graph_indices_repo,
        "get_knowledge_graph_index_by_id",
        fake_get_graph,
    )

    with pytest.raises(ValueError, match="used in a simulation"):
        await knowledge_graph_builds_service.queue_knowledge_graph_build_srvc(
            5,
            session,
            rebuild=True,
        )


@pytest.mark.asyncio
async def test_cancel_check_raises_for_requested_job(recording_async_session_factory):
    job = SimpleNamespace(cancel_requested=True)
    session = recording_async_session_factory()

    with pytest.raises(knowledge_graph_builds_service.KnowledgeGraphBuildCancelled):
        await knowledge_graph_builds_service._raise_if_cancel_requested(
            job,
            session,
        )

    assert session.refreshed == [job]


def test_require_persisted_graph_rejects_empty_generation():
    with pytest.raises(
        ValueError,
        match=(
            "Neo4j persistence produced an empty graph "
            r"\(nodes=0, relationships=0\)"
        ),
    ):
        knowledge_graph_builds_service._require_persisted_graph(
            {"node_count": 0, "relationship_count": 0}
        )


def test_require_persisted_graph_accepts_generation_with_nodes():
    knowledge_graph_builds_service._require_persisted_graph(
        {"node_count": 1, "relationship_count": 0}
    )
