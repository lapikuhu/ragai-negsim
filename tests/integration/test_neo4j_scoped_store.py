import pytest


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