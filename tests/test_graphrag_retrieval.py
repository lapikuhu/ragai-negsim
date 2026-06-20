import pytest

from app.airag.knowledge_graph.retrieval import (
    Evidence,
    ScopedGraphRetriever,
    reciprocal_rank_fusion,
    validate_scoped_cypher,
)
from app.airag.rag_profiles.definitions import normalize_rag_profile_config


def test_graphrag_profile_defaults_to_semantic_retrieval():
    config = normalize_rag_profile_config("graphrag", {})

    assert {
        key: config[key]
        for key in ("retrieval_mode", "evidence_limit", "traversal_depth", "rrf_k")
    } == {
        "retrieval_mode": "semantic",
        "evidence_limit": 6,
        "traversal_depth": 2,
        "rrf_k": 60,
    }
    assert "llm_components" in config


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


def test_graphrag_documents_include_ledger_metadata():
    class FakeGraphStore:
        def structured_query(self, _query, param_map):
            return [{"document_chunk_id": 7, "score": 0.88}]

    class FakeEmbeddingModel:
        def get_query_embedding(self, _query):
            return [0.1, 0.2]

    class FakeChunk:
        content = "Pricing evidence"
        chunk_metadata = {"source": "pricing.md"}
        raw_document_id = 3
        chunk_index = 2

    retriever = ScopedGraphRetriever(
        graph_store=FakeGraphStore(),
        graph_id=12,
        generation="gen-1",
        embedding_model=FakeEmbeddingModel(),
        llm=None,
        chunks_by_id={7: FakeChunk()},
        mode="semantic",
    )

    docs = retriever.invoke("pricing")

    assert docs
    metadata = docs[0].metadata
    assert metadata["retrieval_strategy"] == "graphrag"
    assert metadata["retrieval_mode"] in {"semantic", "cypher", "hybrid"}
    assert metadata["graph_id"] == retriever.graph_id
    assert metadata["graph_generation"] == retriever.generation
