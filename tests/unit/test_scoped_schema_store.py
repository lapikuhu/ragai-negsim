def test_disabled_scoped_schema_refresh_does_not_query_neo4j():
    from app.airag.knowledge_graph.scoped_schema_store import (
        ScopedSchemaNeo4jPropertyGraphStore,
    )

    class RecordingStore(ScopedSchemaNeo4jPropertyGraphStore):
        def structured_query(self, query, param_map=None):
            raise AssertionError(f"Unexpected schema query: {query}")

    store = object.__new__(RecordingStore)
    store.graph_id = 7
    store.generation = "generation-a"
    store._schema_refresh_enabled = False
    store.structured_schema = {}

    store.refresh_schema()

    assert store.structured_schema == {}


def test_enabled_scoped_schema_refresh_queries_only_its_generation():
    from app.airag.knowledge_graph.scoped_schema_store import (
        ScopedSchemaNeo4jPropertyGraphStore,
    )

    class RecordingStore(ScopedSchemaNeo4jPropertyGraphStore):
        def __init__(self):
            self.graph_id = 7
            self.generation = "generation-a"
            self._schema_refresh_enabled = True
            self.structured_schema = {}
            self.queries = []

        def structured_query(self, query, param_map=None):
            self.queries.append((query, param_map))
            if "UNWIND keys(n) AS property" in query:
                return [
                    {
                        "output": {
                            "labels": "Topic",
                            "properties": [{"property": "name", "type": "STRING"}],
                        }
                    }
                ]
            if "UNWIND keys(rel) AS property" in query:
                return [
                    {
                        "output": {
                            "type": "RELATES_TO",
                            "properties": [{"property": "weight", "type": "INTEGER"}],
                        }
                    }
                ]
            if "UNWIND labels(source) AS start" in query:
                return [{"output": {"start": "Topic", "type": "RELATES_TO", "end": "Topic"}}]
            if "count(DISTINCT n)" in query:
                return [{"output": {"name": "Topic", "count": 1}}]
            if "count(DISTINCT rel)" in query:
                return [{"output": {"name": "RELATES_TO", "count": 1}}]
            if "MATCH (n:`Topic`)" in query:
                return [{"output": {"name": {"values": ["alpha"], "distinct_count": 1}}}]
            if "MATCH (source)-[n:`RELATES_TO`]->(target)" in query:
                return [{"output": {"weight": {"min": "1", "max": "1", "distinct_count": 1}}}]
            raise AssertionError(f"Unexpected schema query: {query}")

    store = RecordingStore()

    store.refresh_schema()

    assert store.structured_schema["node_props"]["Topic"][0]["values"] == ["alpha"]
    assert store.structured_schema["rel_props"]["RELATES_TO"][0]["min"] == "1"
    assert store.structured_schema["relationships"] == [
        {"start": "Topic", "type": "RELATES_TO", "end": "Topic"}
    ]
    assert store.structured_schema["metadata"] == {"constraint": [], "index": []}
    assert all("$graph_id" in query and "$generation" in query for query, _ in store.queries)
    assert all(
        forbidden not in query
        for query, _ in store.queries
        for forbidden in ("apoc.meta.data", "apoc.meta.subGraph", "SHOW CONSTRAINTS", "apoc.schema.nodes")
    )


def test_scoped_schema_property_queries_materialize_aggregates_before_returning_maps():
    from app.airag.knowledge_graph.scoped_schema_store import (
        ScopedSchemaNeo4jPropertyGraphStore,
    )

    node_query = ScopedSchemaNeo4jPropertyGraphStore._node_properties_query()
    relationship_query = ScopedSchemaNeo4jPropertyGraphStore._relationship_properties_query()

    assert "WITH label, collect({property: property, type: head(types)}) AS properties" in node_query
    assert "properties: properties" in node_query
    assert "WITH rel_type, collect({property: property, type: head(types)}) AS properties" in relationship_query
    assert "properties: properties" in relationship_query
