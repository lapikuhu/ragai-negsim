import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from langchain_core.documents import Document


_FORBIDDEN_CYPHER = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV|FOREACH|CALL)\b",
    re.IGNORECASE,
)

# Evidence represents a piece of evidence retrieved from the knowledge graph.
@dataclass
class Evidence:
    document_chunk_id: int
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None

# Reciprocal rank fusion (RRF) is a method for combining multiple ranked 
# lists of items into a single ranked list.
def reciprocal_rank_fusion(
    rankings: Iterable[list[Evidence]],
    *,
    limit: int,
    rrf_k: int = 60,
) -> list[Evidence]:
    """
    Perform reciprocal rank fusion on multiple rankings of evidence.
    Args:
        rankings (Iterable[list[Evidence]]): An iterable of lists of 
            Evidence instances.
        limit (int): The maximum number of evidence items to return.
        rrf_k (int): The reciprocal rank fusion parameter.
    Returns:
        A list of Evidence instances representing the fused rankings.
    """
    scores: dict[int, float] = {}
    evidence_by_id: dict[int, Evidence] = {}
    for ranking in rankings:
        for rank, evidence in enumerate(ranking, start=1):
            chunk_id = evidence.document_chunk_id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
            existing = evidence_by_id.get(chunk_id)
            if existing is None:
                evidence_by_id[chunk_id] = Evidence(
                    document_chunk_id=chunk_id,
                    content=evidence.content,
                    metadata=dict(evidence.metadata),
                )
            else:
                existing.metadata.update(evidence.metadata)
    ordered_ids = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
    results = []
    for chunk_id in ordered_ids[:limit]:
        item = evidence_by_id[chunk_id]
        item.score = scores[chunk_id]
        results.append(item)
    return results


def validate_scoped_cypher(query: str, *, max_limit: int = 100) -> str:
    """
    Validate a scoped Cypher query for the knowledge graph.
    Args:
        query (str): The Cypher query to validate.
        max_limit (int): The maximum allowed LIMIT value in the query.
    Returns:
        The validated Cypher query.
    Raises:
        ValueError: If the query is invalid or exceeds the maximum limit.
    """
    stripped = query.strip().rstrip(";")
    if not stripped:
        raise ValueError("Cypher query must not be blank")
    if _FORBIDDEN_CYPHER.search(stripped):
        raise ValueError("Cypher query contains a forbidden write or procedure clause")
    if not re.search(r"\bMATCH\b", stripped, re.IGNORECASE):
        raise ValueError("Cypher query must contain MATCH")
    if not re.search(r"\bRETURN\b", stripped, re.IGNORECASE):
        raise ValueError("Cypher query must contain RETURN")
    required_scope = (
        "knowledge_graph_index_id",
        "graph_generation",
        "$graph_id",
        "$generation",
    )
    if any(value not in stripped for value in required_scope):
        raise ValueError("Cypher query must be scoped to graph id and generation")
    limits = [
        int(value)
        for value in re.findall(r"\bLIMIT\s+(\d+)", stripped, re.IGNORECASE)
    ]
    if not limits:
        raise ValueError("Cypher query must include a LIMIT")
    if max(limits) > max_limit:
        raise ValueError(f"Cypher LIMIT must not exceed {max_limit}")
    return query


def collect_document_chunk_ids(value: Any) -> set[int]:
    """
    Recursively collect all document chunk IDs from a nested structure.
    Args:
        value (Any): The value to search for document chunk IDs.
    Returns:
        A set of document chunk IDs found in the value.
    """ 
    found: set[int] = set()
    if isinstance(value, dict):
        chunk_id = value.get("document_chunk_id")
        if isinstance(chunk_id, int):
            found.add(chunk_id)
        for nested in value.values():
            found.update(collect_document_chunk_ids(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found.update(collect_document_chunk_ids(nested))
    return found


class ScopedGraphRetriever:
    def __init__(
        self,
        *,
        graph_store,
        graph_id: int,
        generation: str,
        embedding_model,
        llm,
        chunks_by_id: dict[int, Any],
        mode: str = "semantic",
        evidence_limit: int = 6,
        traversal_depth: int = 2,
        rrf_k: int = 60,
    ):
        self.graph_store = graph_store
        self.graph_id = graph_id
        self.generation = generation
        self.embedding_model = embedding_model
        self.llm = llm
        self.chunks_by_id = chunks_by_id
        self.mode = mode
        self.evidence_limit = evidence_limit
        self.traversal_depth = traversal_depth
        self.rrf_k = rrf_k

    def _evidence(self, chunk_ids: Iterable[int]) -> list[Evidence]:
        """
        Collect evidence for the given document chunk IDs.
        Args:
            chunk_ids (Iterable[int]): An iterable of document chunk IDs.
        Returns:
            A list of Evidence instances representing the collected evidence.
        """
        evidence = []
        for chunk_id in chunk_ids:
            chunk = self.chunks_by_id.get(chunk_id)
            if chunk is None:
                continue
            evidence.append(
                Evidence(
                    document_chunk_id=chunk_id,
                    content=chunk.content,
                    metadata={
                        **dict(chunk.chunk_metadata),
                        "document_chunk_id": chunk_id,
                        "raw_document_id": chunk.raw_document_id,
                        "chunk_index": chunk.chunk_index,
                    },
                )
            )
        return evidence

    def _semantic(self, query: str) -> list[Evidence]:
        """
        Perform a semantic search for the given query.
        Args:
            query (str): The query string.
        Returns:
            A list of Evidence instances representing the search results.
        """
        embedding = self.embedding_model.get_query_embedding(query)
        rows = self.graph_store.structured_query(
            """
            MATCH (e:`__Entity__`)
            WHERE e.knowledge_graph_index_id = $graph_id
              AND e.graph_generation = $generation
              AND e.embedding IS NOT NULL
            WITH e, vector.similarity.cosine(e.embedding, $embedding) AS score
            ORDER BY score DESC
            LIMIT toInteger($entity_limit)
            MATCH (c)-[:MENTIONS]->(e)
            WHERE c.knowledge_graph_index_id = $graph_id
              AND c.graph_generation = $generation
              AND c.document_chunk_id IS NOT NULL
            RETURN DISTINCT c.document_chunk_id AS document_chunk_id,
                   max(score) AS score
            ORDER BY score DESC
            LIMIT toInteger($evidence_limit)
            """,
            param_map={
                "graph_id": self.graph_id,
                "generation": self.generation,
                "embedding": embedding,
                "entity_limit": max(self.evidence_limit * self.traversal_depth, 10),
                "evidence_limit": self.evidence_limit,
            },
        )
        evidence = self._evidence(
            row["document_chunk_id"]
            for row in rows
            if isinstance(row.get("document_chunk_id"), int)
        )
        scores = {
            row["document_chunk_id"]: row.get("score")
            for row in rows
            if isinstance(row.get("document_chunk_id"), int)
        }
        for item in evidence:
            item.score = scores.get(item.document_chunk_id)
        return evidence

    def _cypher(self, query: str) -> list[Evidence]:
        """
        Perform a Cypher query for the given query.
        Args:
            query (str): The query string.
        Returns:
            A list of Evidence instances representing the query results.
        """
        prompt = f"""
Write one read-only Cypher query answering the question below.
The query must:
- use MATCH and RETURN only;
- never use CALL or any write clause;
- filter every matched node with
  knowledge_graph_index_id = $graph_id and graph_generation = $generation;
- follow MENTIONS relationships to source chunks;
- return source.document_chunk_id AS document_chunk_id;
- include LIMIT {self.evidence_limit}.
Return Cypher only.

Question: {query}
""".strip()
        response = self.llm.complete(prompt)
        cypher = getattr(response, "text", str(response)).strip()
        if cypher.startswith("```"):
            cypher = re.sub(r"^```(?:cypher)?\s*|\s*```$", "", cypher).strip()
        validate_scoped_cypher(cypher, max_limit=self.evidence_limit)
        rows = self.graph_store.structured_query(
            cypher,
            param_map={
                "graph_id": self.graph_id,
                "generation": self.generation,
            },
        )
        chunk_ids: list[int] = []
        for row in rows:
            direct = row.get("document_chunk_id")
            if isinstance(direct, int):
                chunk_ids.append(direct)
            chunk_ids.extend(sorted(collect_document_chunk_ids(row)))
        return self._evidence(dict.fromkeys(chunk_ids))

    def retrieve(self, query: str) -> list[Evidence]:
        """
        Retrieve evidence for the given query.
        Args:
            query (str): The query string.
        Returns:
            A list of Evidence instances representing the retrieval results.
        """
        if self.mode == "semantic":
            return self._semantic(query)
        if self.mode == "cypher":
            return self._cypher(query)
        if self.mode == "hybrid":
            results = []
            errors = []
            for retrieve in (self._semantic, self._cypher):
                try:
                    results.append(retrieve(query))
                except Exception as exc:
                    errors.append(exc)
            if not results:
                raise ValueError("GraphRAG retrieval failed") from errors[-1]
            return reciprocal_rank_fusion(
                results,
                limit=self.evidence_limit,
                rrf_k=self.rrf_k,
            )
        raise ValueError(f"Unsupported GraphRAG retrieval mode: {self.mode}")

    def invoke(self, query: str) -> list[Document]:
        """
        Invoke the GraphRAG retrieval for the given query and return the 
        results as Document instances.
        Args:
            query (str): The query string.
        Returns:
            A list of Document instances representing the retrieval results.
        """
        return [
            Document(
                page_content=item.content,
                metadata={
                    **item.metadata,
                    "retrieval_strategy": "graphrag",
                    "retrieval_mode": self.mode,
                    "graph_id": self.graph_id,
                    "graph_generation": self.generation,
                    "document_chunk_id": item.document_chunk_id,
                    "score": item.score,
                    "evidence_path": self.mode,
                },
            )
            for item in self.retrieve(query)
        ]
