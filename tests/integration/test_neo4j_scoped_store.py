import pytest

from app.airag.knowledge_graph.scoped_schema_store import (
    ScopedSchemaNeo4jPropertyGraphStore,
)


@pytest.mark.integration
@pytest.mark.neo4j
def test_scoped_store_roundtrip_counts_and_cleanup(scoped_neo4j_store):
    scoped_neo4j_store.structured_query(
        """
        CREATE (n:IntegrationNode {
            knowledge_graph_index_id: $graph_id,
            graph_generation: $generation,
            name: 'alpha'
        })
        """,
        param_map={
            "graph_id": scoped_neo4j_store.graph_id,
            "generation": scoped_neo4j_store.generation,
        },
    )

    stats_after_insert = scoped_neo4j_store.generation_stats()

    assert stats_after_insert["node_count"] == 1
    assert stats_after_insert["relationship_count"] == 0

    scoped_neo4j_store.delete_generation()
    stats_after_delete = scoped_neo4j_store.generation_stats()

    assert stats_after_delete["node_count"] == 0
    assert stats_after_delete["relationship_count"] == 0


@pytest.mark.integration
@pytest.mark.neo4j
def test_scoped_schema_refresh_excludes_other_generations_and_database_metadata(
    scoped_neo4j_store,
    neo4j_cfg,
):
    other_store = ScopedSchemaNeo4jPropertyGraphStore(
        graph_id=scoped_neo4j_store.graph_id + 1,
        generation="other-generation",
        username=neo4j_cfg["username"],
        password=neo4j_cfg["password"],
        url=neo4j_cfg["uri"],
        database=neo4j_cfg["database"],
    )
    other_store.delete_generation()
    try:
        scoped_neo4j_store.structured_query(
            """
            CREATE (a:ScopedTopicA {
                knowledge_graph_index_id: $graph_id,
                graph_generation: $generation,
                name: 'alpha'
            })-[:SCOPED_RELATES {weight: 1}]->(b:ScopedTopicA {
                knowledge_graph_index_id: $graph_id,
                graph_generation: $generation,
                name: 'beta'
            })
            """,
            param_map={
                "graph_id": scoped_neo4j_store.graph_id,
                "generation": scoped_neo4j_store.generation,
            },
        )
        other_store.structured_query(
            """
            CREATE (:ScopedTopicB {
                knowledge_graph_index_id: $graph_id,
                graph_generation: $generation,
                private_code: 'other-only'
            })
            """,
            param_map={
                "graph_id": other_store.graph_id,
                "generation": other_store.generation,
            },
        )

        scoped_neo4j_store._schema_refresh_enabled = True
        scoped_neo4j_store.refresh_schema()

        schema = scoped_neo4j_store.structured_schema
        assert "ScopedTopicA" in schema["node_props"]
        assert "ScopedTopicB" not in schema["node_props"]
        assert "SCOPED_RELATES" in schema["rel_props"]
        assert schema["relationships"] == [
            {"start": "ScopedTopicA", "type": "SCOPED_RELATES", "end": "ScopedTopicA"}
        ]
        assert schema["metadata"] == {"constraint": [], "index": []}
    finally:
        other_store.delete_generation()
        other_store.close()
