"""Scoped LlamaIndex schema support for immutable logical knowledge graphs.

Severity: this module is a critical isolation and upstream-compatibility
boundary.  LlamaIndex's native Neo4j ``refresh_schema`` implementation
inspects the entire database, which is incorrect for this application's
property-scoped graph generations.  Do not reintroduce the native refresh on
logical knowledge-graph paths.  Upgrade the LlamaIndex graph-store package
only after the scoped-schema tests verify its cache contract still holds.

Neo4j indexes and constraints are database-wide.  
"""

from typing import Any

import neo4j
from llama_index.core.graph_stores.utils import LIST_LIMIT
from llama_index.graph_stores.neo4j.neo4j_property_graph import (
    BASE_ENTITY_LABEL,
    BASE_NODE_LABEL,
    DISTINCT_VALUE_LIMIT,
    EXCLUDED_LABELS,
    EXCLUDED_RELS,
    EXHAUSTIVE_SEARCH_LIMIT,
    LONG_TEXT_THRESHOLD,
)

from app.airag.knowledge_graph.scoped_store import ScopedNeo4jPropertyGraphStore


class ScopedSchemaNeo4jPropertyGraphStore(ScopedNeo4jPropertyGraphStore):
    """
    A scoped store with an opt-in, in-memory LlamaIndex schema cache.

    Schema refresh is disabled by default because current build and GraphRAG
    retrieval flows do not consume ``structured_schema``.  A future
    schema-aware retriever may opt in with ``schema_refresh_enabled=True``;
    its cache will contain only this store's graph ID and generation.
    """

    def __init__(
        self,
        *,
        schema_refresh_enabled: bool = False, # override default to disable schema refresh
        **kwargs: Any,
    ) -> None:
        self._schema_refresh_enabled = schema_refresh_enabled
        # The parent calls refresh_schema during construction by default.  It
        # must never invoke LlamaIndex's database-wide implementation.
        kwargs.pop("refresh_schema", None) # replace with our own refresh_schema() method
        super().__init__(refresh_schema=False, **kwargs)
        if schema_refresh_enabled:
            self.refresh_schema()

    def refresh_schema(self) -> None:
        """
        Refresh the LlamaIndex schema cache for this generation only.
        """
        if not self._schema_refresh_enabled:
            return

        params = {
            "graph_id": self.graph_id,
            "generation": self.generation,
            "excluded_labels": [
                *EXCLUDED_LABELS,
                BASE_ENTITY_LABEL,
                BASE_NODE_LABEL,
            ],
            "excluded_relationships": EXCLUDED_RELS,
        }
        node_properties = self._schema_rows(self._node_properties_query(), params)
        relationship_properties = self._schema_rows(
            self._relationship_properties_query(), params
        )
        relationships = self._schema_rows(self._relationship_patterns_query(), params)

        self.structured_schema = {
            "node_props": {
                row["output"]["labels"]: row["output"]["properties"]
                for row in node_properties
            },
            "rel_props": {
                row["output"]["type"]: row["output"]["properties"]
                for row in relationship_properties
            },
            "relationships": [row["output"] for row in relationships],
            # Constraints and indexes describe the physical Neo4j database,
            # not one property-scoped logical generation.
            "metadata": {"constraint": [], "index": []},
        }

        self._enrich_node_properties(params)
        self._enrich_relationship_properties(params)

    def _schema_rows(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Return the result of a structured query.

        Args:
            query (str): The Cypher query string.
            params (dict[str, Any]): The query parameters.
        Returns:
            list[dict[str, Any]]: The query result rows.
        """
        return self.structured_query(query, param_map=params) or []

    def _enrich_node_properties(self, params: dict[str, Any]) -> None:
        """
        Enrich the node properties with additional metadata.
        Args:
            params (dict[str, Any]): The query parameters.
        Returns:
            None
        """
        for row in self._schema_rows(self._node_counts_query(), params):
            node = row["output"]
            node_props = self.structured_schema["node_props"].get(node["name"])
            if not node_props:
                continue
            enhanced = self._schema_rows(
                self._enhanced_schema_cypher(
                    node["name"],
                    node_props,
                    node["count"] < EXHAUSTIVE_SEARCH_LIMIT,
                ),
                params,
            )
            if enhanced:
                self._apply_enhanced_properties(node_props, enhanced[0]["output"])

    def _enrich_relationship_properties(self, params: dict[str, Any]) -> None:
        """
        Enrich the relationship properties with additional metadata.
        Args:
            params (dict[str, Any]): The query parameters.
        Returns:
            None
        """
        for row in self._schema_rows(self._relationship_counts_query(), params):
            relationship = row["output"]
            relationship_props = self.structured_schema["rel_props"].get(
                relationship["name"]
            )
            if not relationship_props:
                continue
            try:
                enhanced = self._schema_rows(
                    self._enhanced_schema_cypher(
                        relationship["name"],
                        relationship_props,
                        relationship["count"] < EXHAUSTIVE_SEARCH_LIMIT,
                        is_relationship=True,
                    ),
                    params,
                )
            except neo4j.exceptions.ClientError:
                continue
            if enhanced:
                self._apply_enhanced_properties(relationship_props, enhanced[0]["output"])

    @staticmethod
    def _apply_enhanced_properties(
        properties: list[dict[str, Any]], enhanced_info: dict[str, Any]
    ) -> None:
        """
        Apply enhanced properties to the given list of properties.

        Args:
            properties (list[dict[str, Any]]): The list of properties to enrich.
            enhanced_info (dict[str, Any]): The enhanced information for the properties.
        Returns:
            None
        """
        for prop in properties:
            prop_name = prop["property"]
            info = enhanced_info.get(prop_name)
            if info is None:
                continue
            if prop["type"] == "STRING" and any(
                len(value) >= LONG_TEXT_THRESHOLD for value in info.get("values", [])
            ):
                prop["type"] = "TEXT"
            if prop["type"] == "LIST" and info.get("max_size", 0) > LIST_LIMIT:
                prop["type"] = "EMBEDDING"
            prop.update(info)

    @staticmethod
    def _quote(value: str) -> str:
        """
        Format a string value for use in Cypher queries by escaping backticks.
        Args:
            value (str): The string value to format.
        Returns:
            str: The formatted string value.
        """
        return value.replace("`", "``")

    def _enhanced_schema_cypher(
        self,
        label_or_type: str,
        properties: list[dict[str, Any]],
        exhaustive: bool,
        *,
        is_relationship: bool = False,
    ) -> str:
        """
        Generate the Cypher query for the enhanced schema of a node or relationship.
        Args:
            label_or_type (str): The label of the node or type of the 
                relationship.
            properties (list[dict[str, Any]]): The list of properties 
                for the schema.
            exhaustive (bool): Whether to include all properties or 
                limit the output.
            is_relationship (bool): Whether the schema is for a relationship.
        Returns:
            str: The generated Cypher query.
        """
        escaped = self._quote(label_or_type)
        if is_relationship:# Scope the match clause
            match_clause = ( 
                f"MATCH (source)-[n:`{escaped}`]->(target)\n"
                "WHERE source.knowledge_graph_index_id = $graph_id\n"
                "  AND source.graph_generation = $generation\n"
                "  AND target.knowledge_graph_index_id = $graph_id\n"
                "  AND target.graph_generation = $generation"
            )
        else:
            match_clause = (
                f"MATCH (n:`{escaped}`)\n"
                "WHERE n.knowledge_graph_index_id = $graph_id\n"
                "  AND n.graph_generation = $generation"
            )

        if not exhaustive:
            match_clause += "\nWITH n LIMIT 5"

        with_clauses: list[str] = []
        output: dict[str, str] = {}
        for prop in properties:
            prop_name = prop["property"]
            prop_type = prop["type"]
            escaped_prop = self._quote(prop_name)
            if prop_type == "STRING":
                with_clauses.append(
                    "collect(distinct substring(toString(coalesce(" 
                    f"n.`{escaped_prop}`, '')), 0, {LONG_TEXT_THRESHOLD})) "
                    f"AS `{escaped_prop}_values`"
                )
                output[prop_name] = (
                    f"{{values: `{escaped_prop}_values`[..{DISTINCT_VALUE_LIMIT}], "
                    f"distinct_count: size(`{escaped_prop}_values`)}}"
                )
            elif prop_type in {
                "INTEGER",
                "FLOAT",
                "DATE",
                "DATE_TIME",
                "LOCAL_DATE_TIME",
            }:
                with_clauses.extend(
                    [
                        f"min(n.`{escaped_prop}`) AS `{escaped_prop}_min`",
                        f"max(n.`{escaped_prop}`) AS `{escaped_prop}_max`",
                        f"count(distinct n.`{escaped_prop}`) AS `{escaped_prop}_distinct`",
                    ]
                )
                output[prop_name] = (
                    f"{{min: toString(`{escaped_prop}_min`), "
                    f"max: toString(`{escaped_prop}_max`), "
                    f"distinct_count: `{escaped_prop}_distinct`}}"
                )
            elif prop_type == "LIST":
                with_clauses.extend(
                    [
                        f"min(size(coalesce(n.`{escaped_prop}`, []))) AS `{escaped_prop}_size_min`",
                        f"max(size(coalesce(n.`{escaped_prop}`, []))) AS `{escaped_prop}_size_max`",
                        f"collect(n.`{escaped_prop}`)[0][..3] AS `{escaped_prop}_values`",
                    ]
                )
                output[prop_name] = (
                    f"{{min_size: `{escaped_prop}_size_min`, "
                    f"max_size: `{escaped_prop}_size_max`, "
                    f"values: `{escaped_prop}_values`}}"
                )

        if not with_clauses:
            return "RETURN {} AS output"
        return (
            f"{match_clause}\nWITH "
            + ",\n     ".join(with_clauses)
            + "\nRETURN {"
            + ", ".join(f"`{self._quote(name)}`: {value}" for name, value in output.items())
            + "} AS output"
        )

### QUERIES

    @staticmethod
    def _node_properties_query() -> str:
        """
        Get the properties of nodes in the knowledge graph.

        Returns:
            A dictionary containing node labels and their properties.
        """
        return """
        MATCH (n)
        WHERE n.knowledge_graph_index_id = $graph_id
          AND n.graph_generation = $generation
        UNWIND labels(n) AS label
        WITH n, label
        WHERE NOT label IN $excluded_labels
        UNWIND keys(n) AS property
        WITH label, property, collect(DISTINCT CASE
            WHEN valueType(n[property]) STARTS WITH 'LIST<' THEN 'LIST'
            WHEN valueType(n[property]) = 'LOCAL DATETIME NOT NULL' THEN 'LOCAL_DATE_TIME'
            WHEN valueType(n[property]) = 'ZONED DATETIME NOT NULL' THEN 'DATE_TIME'
            ELSE replace(valueType(n[property]), ' NOT NULL', '')
        END) AS types
        WITH label, collect({property: property, type: head(types)}) AS properties
        RETURN {
            labels: label,
            properties: properties
        } AS output
        """

    @staticmethod
    def _relationship_properties_query() -> str:
        """
        Get the properties of relationships in the knowledge graph.
        Returns:
            A dictionary containing relationship types and their properties.
        """
        return """
        MATCH (source)-[rel]->(target)
        WHERE source.knowledge_graph_index_id = $graph_id
          AND source.graph_generation = $generation
          AND target.knowledge_graph_index_id = $graph_id
          AND target.graph_generation = $generation
        UNWIND keys(rel) AS property
        WITH type(rel) AS rel_type, property,
             collect(DISTINCT CASE
                WHEN valueType(rel[property]) STARTS WITH 'LIST<' THEN 'LIST'
                WHEN valueType(rel[property]) = 'LOCAL DATETIME NOT NULL' THEN 'LOCAL_DATE_TIME'
                WHEN valueType(rel[property]) = 'ZONED DATETIME NOT NULL' THEN 'DATE_TIME'
                ELSE replace(valueType(rel[property]), ' NOT NULL', '')
             END) AS types
        WITH rel_type, collect({property: property, type: head(types)}) AS properties
        RETURN {
            type: rel_type,
            properties: properties
        } AS output
        """

    @staticmethod
    def _relationship_patterns_query() -> str:
        """
        Get the relationship patterns in the knowledge graph.

        Returns:
            A list of relationship patterns with start and end node 
            labels and relationship types.
        """
        return """
        MATCH (source)-[rel]->(target)
        WHERE source.knowledge_graph_index_id = $graph_id
          AND source.graph_generation = $generation
          AND target.knowledge_graph_index_id = $graph_id
          AND target.graph_generation = $generation
        UNWIND labels(source) AS start
        UNWIND labels(target) AS end
        WITH start, type(rel) AS rel_type, end
        WHERE NOT start IN $excluded_labels
          AND NOT end IN $excluded_labels
          AND NOT rel_type IN $excluded_relationships
        RETURN DISTINCT {start: start, type: rel_type, end: end} AS output
        """

    @staticmethod
    def _node_counts_query() -> str:
        """
        Get the counts of nodes in the knowledge graph.
        Returns:
            A list of node labels with their respective counts.
        """
        return """
        MATCH (n)
        WHERE n.knowledge_graph_index_id = $graph_id
          AND n.graph_generation = $generation
        UNWIND labels(n) AS label
        WITH label, count(DISTINCT n) AS count
        WHERE NOT label IN $excluded_labels
        RETURN {name: label, count: count} AS output
        """

    @staticmethod
    def _relationship_counts_query() -> str:
        """
        Get the counts of relationships in the knowledge graph.
        Returns:
            A list of relationship types with their respective counts.
        """
        return """
        MATCH (source)-[rel]->(target)
        WHERE source.knowledge_graph_index_id = $graph_id
          AND source.graph_generation = $generation
          AND target.knowledge_graph_index_id = $graph_id
          AND target.graph_generation = $generation
        WITH type(rel) AS name, count(DISTINCT rel) AS count
        WHERE NOT name IN $excluded_relationships
        RETURN {name: name, count: count} AS output
        """
