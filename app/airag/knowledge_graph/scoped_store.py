from copy import deepcopy
from typing import Sequence

from llama_index.core.graph_stores.types import (
    ChunkNode,
    EntityNode,
    LabelledNode,
    Relation,
    TRIPLET_SOURCE_KEY,
)
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore


class ScopedNeo4jPropertyGraphStore(Neo4jPropertyGraphStore):
    """
    Isolate a logical graph generation inside one Neo4j database.

    LlamaIndex identifies entities globally by name. This wrapper prefixes
    graph identities before persistence while retaining display names and
    scope properties for retrieval and cleanup.
    """

    def __init__(self, *, graph_id: int, generation: str, **kwargs):
        self.graph_id = graph_id
        self.generation = generation
        self.scope_prefix = f"kg:{graph_id}:{generation}:"
        super().__init__(**kwargs)

    def _scope_id(self, value: str) -> str:
        """
        Scope a graph identity by prefixing it with the knowledge graph 
        ID and generation.
        Args:
            value (str): The original graph identity.
        Returns:
            A scoped graph identity string.
        """
        if value.startswith(self.scope_prefix):
            return value
        return f"{self.scope_prefix}entity:{value}"

    def _scope_properties(self, properties: dict) -> dict:
        """
        Scope the properties of a graph node by adding the knowledge graph ID
        and generation, and scoping the source ID if present.
        Args:
            properties (dict): The original properties of the node.
        Returns:
            A dictionary of scoped properties.
        """
        scoped = {
            **properties,
            "knowledge_graph_index_id": self.graph_id,
            "graph_generation": self.generation,
        }
        source_id = scoped.get(TRIPLET_SOURCE_KEY)
        if source_id:
            scoped[TRIPLET_SOURCE_KEY] = self._scope_id(str(source_id))
        return scoped

    def get(
        self,
        properties: dict | None = None,
        ids: list[str] | None = None,
    ) -> list[LabelledNode]:
        """
        Retrieve nodes from the graph store with scoped properties and IDs.
        Args:
            properties (dict | None): The properties to filter nodes.
            ids (list[str] | None): The IDs of the nodes to retrieve.
        Returns:
            A list of LabelledNode instances with scoped properties and IDs.
        """
        scoped_properties = {
            **(properties or {}),
            "knowledge_graph_index_id": self.graph_id,
            "graph_generation": self.generation,
        }
        scoped_ids = [self._scope_id(value) for value in ids] if ids else None
        return super().get(properties=scoped_properties, ids=scoped_ids)

    def upsert_nodes(self, nodes: Sequence[LabelledNode]) -> None:
        """
        Upsert nodes into the graph store with scoped properties and IDs.
        Args:
            nodes (Sequence[LabelledNode]): The nodes to upsert.
        Returns:
            None
        """
        scoped_nodes: list[LabelledNode] = []
        for source in nodes:
            node = deepcopy(source)
            node.properties = self._scope_properties(node.properties)
            if isinstance(node, EntityNode):
                original_name = node.name
                node.properties.setdefault("display_name", original_name)
                node.name = self._scope_id(original_name)
            elif isinstance(node, ChunkNode):
                node.id_ = self._scope_id(node.id)
            scoped_nodes.append(node)
        super().upsert_nodes(scoped_nodes)

    def upsert_relations(self, relations: list[Relation]) -> None:
        """
        Upsert relations into the graph store with scoped properties and IDs.
        Args:
            relations (list[Relation]): The relations to upsert.
        Returns:
            None
        """
        scoped_relations = []
        for source in relations:
            relation = deepcopy(source)
            relation.source_id = self._scope_id(relation.source_id)
            relation.target_id = self._scope_id(relation.target_id)
            relation.properties = self._scope_properties(relation.properties)
            scoped_relations.append(relation)
        super().upsert_relations(scoped_relations)

    def delete_generation(self) -> None:
        """
        Delete all nodes and relationships for the current graph generation.
        Returns:
            None
        """
        self.structured_query(
            """
            MATCH (n)
            WHERE n.knowledge_graph_index_id = $graph_id
              AND n.graph_generation = $generation
            DETACH DELETE n
            """,
            param_map={
                "graph_id": self.graph_id,
                "generation": self.generation,
            },
        )

    def generation_stats(self) -> dict[str, int]:
        """
        Return persisted node and relationship counts for this generation.
        """
        rows = self.structured_query(
            """
            MATCH (n)
            WHERE n.knowledge_graph_index_id = $graph_id
              AND n.graph_generation = $generation
            OPTIONAL MATCH (n)-[r]-()
            RETURN count(DISTINCT n) AS node_count,
                   count(DISTINCT r) AS relationship_count
            """,
            param_map={
                "graph_id": self.graph_id,
                "generation": self.generation,
            },
        )
        row = rows[0] if rows else {}
        return {
            "node_count": int(row.get("node_count", 0)),
            "relationship_count": int(row.get("relationship_count", 0)),
        }
