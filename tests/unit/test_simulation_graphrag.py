from types import SimpleNamespace

import pytest

from app.services import simulations_service


@pytest.mark.asyncio
async def test_scoped_graphrag_retriever_disables_schema_refresh(monkeypatch):
    captured = {}

    class Store:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    async def fake_list_chunks(_corpus_index_id, _session):
        return []

    graph = SimpleNamespace(
        id=8,
        active_generation="generation-a",
        corpus_index_id=77,
        build_config={},
    )
    profile = SimpleNamespace(config={"retrieval_mode": "semantic"})

    monkeypatch.setattr(
        simulations_service.document_chunks_repo,
        "list_document_chunks_for_corpus_index",
        fake_list_chunks,
    )
    monkeypatch.setattr(
        simulations_service,
        "ScopedSchemaNeo4jPropertyGraphStore",
        Store,
    )
    monkeypatch.setattr(simulations_service, "create_graph_embedding_model", lambda _: object())
    monkeypatch.setattr(simulations_service, "create_graph_llm", lambda _: object())

    retriever = await simulations_service._make_scoped_graph_retriever(
        graph,
        profile,
        object(),
    )

    assert captured["graph_id"] == 8
    assert captured["generation"] == "generation-a"
    assert captured["schema_refresh_enabled"] is False
    assert retriever.mode == "semantic"


@pytest.mark.asyncio
async def test_validate_graphrag_profile_requires_matching_built_graph(monkeypatch):
    profile = SimpleNamespace(
        strategy="graphrag",
        knowledge_graph_index_id=8,
    )

    async def fake_get_graph(graph_id, session):
        return SimpleNamespace(
            id=graph_id,
            corpus_index_id=77,
            status="built",
            active_generation="g1",
        )

    monkeypatch.setattr(
        simulations_service.knowledge_graph_indices_repo,
        "get_knowledge_graph_index_by_id",
        fake_get_graph,
    )

    graph = await simulations_service._validate_graphrag_profile_for_index(
        profile,
        corpus_index_id=77,
        session=object(),
    )
    assert graph.id == 8

    with pytest.raises(ValueError, match="same corpus index"):
        await simulations_service._validate_graphrag_profile_for_index(
            profile,
            corpus_index_id=78,
            session=object(),
        )
