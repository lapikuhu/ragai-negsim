from app.airag.knowledge_graph.connection import (
    describe_neo4j_error,
    resolve_neo4j_database,
    resolve_neo4j_uri,
)


def test_resolve_neo4j_uri_rewrites_local_routing_scheme_to_bolt():
    assert (
        resolve_neo4j_uri("neo4j://127.0.0.1:7687")
        == "bolt://127.0.0.1:7687"
    )
    assert (
        resolve_neo4j_uri("neo4j://localhost:7687")
        == "bolt://localhost:7687"
    )


def test_resolve_neo4j_uri_preserves_non_local_or_direct_schemes():
    assert (
        resolve_neo4j_uri("neo4j://graph.example.com:7687")
        == "neo4j://graph.example.com:7687"
    )
    assert (
        resolve_neo4j_uri("bolt://127.0.0.1:7687")
        == "bolt://127.0.0.1:7687"
    )


def test_describe_neo4j_error_adds_local_routing_hint():
    detail = describe_neo4j_error(
        ValueError("Unable to retrieve routing information"),
        "neo4j://127.0.0.1:7687",
    )

    assert "Unable to retrieve routing information" in detail
    assert "bolt://127.0.0.1:7687" in detail


def test_resolve_neo4j_database_defaults_to_neo4j():
    assert resolve_neo4j_database(None) == "neo4j"
    assert resolve_neo4j_database("") == "neo4j"
    assert resolve_neo4j_database("analytics") == "analytics"
