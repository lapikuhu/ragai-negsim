from types import SimpleNamespace

import pytest

from app.services import simulations_service


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
