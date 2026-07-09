from types import SimpleNamespace

import pytest

from app.repositories import rag_profiles_repo
from app.schemas.rag_profiles_schemas import RagProfileCreate


@pytest.mark.asyncio
async def test_graphrag_profile_requires_built_graph(monkeypatch):
    async def fake_get_graph(graph_id, session):
        return SimpleNamespace(
            id=graph_id,
            status="created",
            active_generation=None,
        )

    monkeypatch.setattr(
        rag_profiles_repo.knowledge_graph_indices_repo,
        "get_knowledge_graph_index_by_id",
        fake_get_graph,
    )

    with pytest.raises(ValueError, match="built knowledge graph"):
        await rag_profiles_repo.validate_rag_profile_graph_binding(
            strategy="graphrag",
            knowledge_graph_index_id=9,
            session=object(),
        )


@pytest.mark.asyncio
async def test_crag_profile_forbids_graph_reference():
    with pytest.raises(ValueError, match="only valid for GraphRAG"):
        await rag_profiles_repo.validate_rag_profile_graph_binding(
            strategy="crag",
            knowledge_graph_index_id=9,
            session=object(),
        )


def test_rag_profile_create_carries_graph_reference():
    profile = RagProfileCreate(
        name="Graph retrieval",
        strategy="graphrag",
        config={},
        knowledge_graph_index_id=9,
        created_by_user_id=3,
    )

    assert profile.knowledge_graph_index_id == 9
