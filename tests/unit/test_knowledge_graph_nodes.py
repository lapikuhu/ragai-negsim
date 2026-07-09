from types import SimpleNamespace

from llama_index.core.schema import NodeRelationship
from llama_index.core.llms import MockLLM

from app.airag.knowledge_graph.k_graph import (
    build_graph_text_nodes,
    create_kg_extractors,
)
from app.airag.knowledge_graph.scoped_store import (
    ScopedNeo4jPropertyGraphStore,
)


def _chunk(chunk_id: int, raw_document_id: int, chunk_index: int, content: str):
    return SimpleNamespace(
        id=chunk_id,
        raw_document_id=raw_document_id,
        chunking_profile_id=4,
        chunk_index=chunk_index,
        content=content,
        chunk_metadata={"header": "Opening"},
    )


def test_build_graph_text_nodes_preserves_provenance_and_adjacency():
    nodes = build_graph_text_nodes(
        [
            _chunk(11, 7, 0, "First"),
            _chunk(12, 7, 1, "Second"),
            _chunk(21, 8, 0, "Other document"),
        ],
        graph_id=3,
        generation="generation-b",
        corpus_index_id=9,
    )

    assert [node.id_ for node in nodes] == [
        "kg:3:generation-b:chunk:11",
        "kg:3:generation-b:chunk:12",
        "kg:3:generation-b:chunk:21",
    ]
    assert nodes[0].metadata["document_chunk_id"] == 11
    assert nodes[0].metadata["corpus_index_id"] == 9
    assert nodes[0].metadata["knowledge_graph_index_id"] == 3
    assert nodes[0].metadata["graph_generation"] == "generation-b"
    assert nodes[0].next_node.node_id == nodes[1].id_
    assert nodes[1].prev_node.node_id == nodes[0].id_
    assert NodeRelationship.NEXT not in nodes[2].relationships


def test_create_extractors_respects_order_and_schema_options():
    llm = MockLLM()
    extractors = create_kg_extractors(
        {
            "extractors": ["implicit", "simple", "schema"],
            "strict_schema": True,
            "max_paths_per_chunk": 4,
        },
        llm=llm,
    )

    assert [extractor.class_name() for extractor in extractors] == [
        "ImplicitPathExtractor",
        "SimpleLLMPathExtractor",
        "SchemaLLMPathExtractor",
    ]
    assert extractors[1].max_paths_per_chunk == 4
    assert extractors[2].max_triplets_per_chunk == 4
    assert extractors[2].strict is True


def test_generation_stats_reports_scoped_neo4j_counts():
    store = object.__new__(ScopedNeo4jPropertyGraphStore)
    store.graph_id = 3
    store.generation = "generation-b"
    captured = {}

    def fake_structured_query(query, param_map):
        captured["query"] = query
        captured["param_map"] = param_map
        return [{"node_count": 4, "relationship_count": 3}]

    store.structured_query = fake_structured_query

    stats = store.generation_stats()

    assert stats == {"node_count": 4, "relationship_count": 3}
    assert captured["param_map"] == {
        "graph_id": 3,
        "generation": "generation-b",
    }
    assert "OPTIONAL MATCH (n)-[r]-()" in captured["query"]
