import pytest

from app.airag.knowledge_graph.retrieval import (
    Evidence,
    reciprocal_rank_fusion,
    validate_scoped_cypher,
)
from app.airag.rag_profiles.definitions import normalize_rag_profile_config


def test_graphrag_profile_defaults_to_semantic_retrieval():
    config = normalize_rag_profile_config("graphrag", {})

    assert config == {
        "retrieval_mode": "semantic",
        "evidence_limit": 6,
        "traversal_depth": 2,
        "rrf_k": 60,
    }


def test_reciprocal_rank_fusion_deduplicates_chunk_evidence():
    semantic = [
        Evidence(document_chunk_id=1, content="one", metadata={}),
        Evidence(document_chunk_id=2, content="two", metadata={}),
    ]
    cypher = [
        Evidence(document_chunk_id=2, content="two", metadata={"path": "x"}),
        Evidence(document_chunk_id=3, content="three", metadata={}),
    ]

    fused = reciprocal_rank_fusion([semantic, cypher], limit=3, rrf_k=60)

    assert [item.document_chunk_id for item in fused] == [2, 1, 3]
    assert fused[0].metadata["path"] == "x"


@pytest.mark.parametrize(
    "query",
    [
        "CREATE (n)",
        "MATCH (n) DELETE n",
        "CALL db.labels()",
        "MATCH (n) RETURN n",
    ],
)
def test_validate_scoped_cypher_rejects_unsafe_or_unscoped_queries(query):
    with pytest.raises(ValueError):
        validate_scoped_cypher(query)


def test_validate_scoped_cypher_accepts_scoped_read_query():
    query = """
    MATCH (n)-[r]-(m)
    WHERE n.knowledge_graph_index_id = $graph_id
      AND n.graph_generation = $generation
      AND m.knowledge_graph_index_id = $graph_id
      AND m.graph_generation = $generation
    RETURN n, r, m LIMIT 20
    """

    assert validate_scoped_cypher(query) == query
