from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.schemas.knowledge_graph_indices_schemas import (
    KnowledgeGraphIndexCreate,
    KnowledgeGraphIndexReadWithUsage,
    KnowledgeGraphIndexUpdate,
    normalize_knowledge_graph_build_config,
)
from app.repositories import knowledge_graph_indices_repo


def test_normalize_graph_config_defaults_to_openai_and_requires_extractor():
    normalized = normalize_knowledge_graph_build_config({})

    assert normalized["llm_provider"] == "openai"
    assert normalized["llm_model"] == "gpt-4o-mini"
    assert normalized["embedding_provider"] == "openai"
    assert normalized["embedding_model"] == "text-embedding-3-small"
    assert normalized["extractors"] == ["schema"]

    with pytest.raises(ValueError, match="at least one extractor"):
        normalize_knowledge_graph_build_config({"extractors": []})


def test_graph_create_rejects_duplicate_extractors_and_unknown_provider():
    with pytest.raises(ValueError, match="duplicate"):
        KnowledgeGraphIndexCreate(
            name="Negotiation graph",
            corpus_index_id=7,
            build_config={"extractors": ["schema", "schema"]},
        )

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        KnowledgeGraphIndexCreate(
            name="Negotiation graph",
            corpus_index_id=7,
            build_config={"llm_provider": "other"},
        )


@pytest.mark.parametrize(
    "extractors",
    [
        ["schema"],
        ["schema", "implicit"],
        ["simple"],
        ["simple", "implicit"],
    ],
)
def test_graph_write_accepts_supported_extractor_combinations(extractors):
    created = KnowledgeGraphIndexCreate(
        name="Negotiation graph",
        corpus_index_id=7,
        build_config={"extractors": extractors},
    )

    assert created.build_config["extractors"] == extractors


@pytest.mark.parametrize(
    ("extractors", "message"),
    [
        (["implicit"], "exactly one semantic extractor"),
        (["schema", "simple"], "exactly one semantic extractor"),
        (["schema", "simple", "implicit"], "exactly one semantic extractor"),
    ],
)
def test_graph_write_rejects_incompatible_extractor_combinations(
    extractors,
    message,
):
    with pytest.raises(ValueError, match=message):
        KnowledgeGraphIndexCreate(
            name="Negotiation graph",
            corpus_index_id=7,
            build_config={"extractors": extractors},
        )

    with pytest.raises(ValueError, match=message):
        KnowledgeGraphIndexUpdate(
            build_config={"extractors": extractors},
        )


def test_graph_read_allows_legacy_implicit_only_configuration():
    graph = KnowledgeGraphIndexReadWithUsage(
        id=3,
        name="Legacy graph",
        corpus_index_id=7,
        build_config={"extractors": ["implicit"]},
        status="built",
        created_at=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
    )

    assert graph.build_config["extractors"] == ["implicit"]


@pytest.mark.asyncio
async def test_ensure_graph_mutable_rejects_permanently_locked_graph():
    graph = SimpleNamespace(
        id=3,
        locked_at=datetime.now(timezone.utc),
    )

    with pytest.raises(ValueError, match="used in a simulation"):
        await knowledge_graph_indices_repo.ensure_knowledge_graph_mutable(
            graph,
            object(),
        )


@pytest.mark.asyncio
async def test_lock_graph_is_idempotent(monkeypatch):
    locked_at = datetime.now(timezone.utc)
    graph = SimpleNamespace(id=3, locked_at=locked_at)
    committed = []

    async def fake_commit_and_refresh(session, value):
        committed.append(value)
        return value

    monkeypatch.setattr(
        knowledge_graph_indices_repo,
        "commit_and_refresh",
        fake_commit_and_refresh,
    )

    result = await knowledge_graph_indices_repo.lock_knowledge_graph(
        graph,
        object(),
    )

    assert result.locked_at == locked_at
    assert committed == []
