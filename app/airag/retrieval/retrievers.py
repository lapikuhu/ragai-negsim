"""Retriever construction, BM25 persistence, and deterministic hybrid fusion."""

import asyncio
import math
import pickle
import zlib
from collections.abc import Awaitable, Callable, Sequence
from hashlib import sha256

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document


BM25_ARTIFACT_FORMAT_VERSION = "pickle-zlib-v1"
MAX_BM25_ARTIFACT_BYTES = 150 * 1024 * 1024


def make_dense_retriever(
    vector_store,
    k: int = 4,
    metadata_filter: dict | None = None,
):
    """Create a langchain retriever from the specified vector store.
    Args:
        vector_store: The vector store instance to use for creating the
            retriever.
        k (int, optional): The number of top documents to retrieve.
            Defaults to 4.
    Returns:
        A langchain retriever instance that can be used to retrieve relevant
        documents based on queries.
    """

    search_kwargs = {"k": k}
    if metadata_filter:
        search_kwargs["filter"] = metadata_filter

    retriever = vector_store.as_retriever(search_kwargs=search_kwargs)
    return retriever


def _require_positive_k(value: int, name: str) -> int:
    """
    Raise a ValueError if the provided value is not a positive integer.
    Args:
        value (int): The value to check.
        name (str): The name of the parameter being checked (for error messages).
    Returns:
        int: The validated positive integer value.
    Raises:
        ValueError: If the value is not a positive integer.
    """
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _document_chunk_id(document: Document) -> int:
    chunk_id = document.metadata.get("document_chunk_id")
    if type(chunk_id) is not int:
        raise ValueError(
            "Retriever documents require integer document_chunk_id metadata"
        )
    return chunk_id


def deduplicate_documents_by_chunk_id(
    documents: Sequence[Document],
) -> list[Document]:
    """
    Keep the first occurrence of each validated document chunk.
    Args:
        documents (Sequence[Document]): The list of documents to deduplicate.
    Returns:
        list[Document]: The deduplicated list of documents, keeping the first 
        occurrence of each chunk.
    """
    deduplicated: list[Document] = []
    seen: set[int] = set()
    for document in documents:
        chunk_id = _document_chunk_id(document)
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        deduplicated.append(document)
    return deduplicated


def make_bm25_retriever(
    documents: list[Document],
    k: int = 4,
) -> BM25Retriever:
    """
    Create a BM25 retriever over existing chunk documents.
    Args:
        documents (list[Document]): The list of documents to create the 
            retriever from.
        k (int, optional): The number of top documents to retrieve. 
            Defaults to 4.
    Returns:
        BM25Retriever: The created BM25 retriever.
    """
    _require_positive_k(k, "k")
    for document in documents:
        _document_chunk_id(document)
    # TODO: Introduce versioned BM25 text normalization/tokenization for documents and queries.
    retriever = BM25Retriever.from_documents(
        documents=documents,
        k=k,
    )
    return retriever


def build_serialized_bm25_artifact(
    documents: list[Document],
    *,
    k: int = 4,
) -> bytes:
    """Build and serialize a trusted BM25 runtime using protocol 5 and zlib."""
    retriever = make_bm25_retriever(documents, k=k)
    artifact = zlib.compress(pickle.dumps(retriever, protocol=5))
    if len(artifact) > MAX_BM25_ARTIFACT_BYTES:
        raise ValueError("BM25 artifact exceeds the 150 MiB size limit")
    return artifact


def load_validated_bm25_artifact(
    artifact: bytes,
    *,
    expected_checksum: str,
    format_version: str,
    expected_document_count: int,
    k: int | None = None,
) -> BM25Retriever:
    """Load trusted artifact bytes after validating persistence metadata."""
    if len(artifact) > MAX_BM25_ARTIFACT_BYTES:
        raise ValueError("BM25 artifact exceeds the 150 MiB size limit")
    if format_version != BM25_ARTIFACT_FORMAT_VERSION:
        raise ValueError(
            f"BM25 artifact format must be {BM25_ARTIFACT_FORMAT_VERSION}"
        )
    if sha256(artifact).hexdigest() != expected_checksum:
        raise ValueError("BM25 artifact checksum does not match persisted metadata")
    if type(expected_document_count) is not int or expected_document_count < 0:
        raise ValueError("BM25 expected document count must be a non-negative integer")

    try:
        payload = zlib.decompress(artifact)
        if not payload.startswith(b"\x80\x05"):
            raise ValueError("BM25 artifact must use pickle protocol 5")
        retriever = pickle.loads(payload)
    except (
        pickle.PickleError,
        AttributeError,
        EOFError,
        ImportError,
        IndexError,
        TypeError,
        ValueError,
        zlib.error,
    ) as exc:
        raise ValueError("BM25 artifact cannot be loaded") from exc

    if not isinstance(retriever, BM25Retriever):
        raise ValueError("BM25 artifact has an unexpected retriever type")
    if len(retriever.docs) != expected_document_count:
        raise ValueError(
            "BM25 artifact document count does not match the chunk snapshot"
        )
    for document in retriever.docs:
        _document_chunk_id(document)
    if k is not None:
        retriever.k = _require_positive_k(k, "k")
    return retriever


async def abuild_serialized_bm25_artifact(
    documents: list[Document],
    *,
    k: int = 4,
    run_in_thread: Callable[..., Awaitable[bytes]] = asyncio.to_thread,
) -> bytes:
    """Build and serialize BM25 outside the event-loop thread."""
    return await run_in_thread(build_serialized_bm25_artifact, documents, k=k)


async def aload_validated_bm25_artifact(
    artifact: bytes,
    *,
    expected_checksum: str,
    format_version: str,
    expected_document_count: int,
    k: int | None = None,
    run_in_thread: Callable[..., Awaitable[BM25Retriever]] = asyncio.to_thread,
) -> BM25Retriever:
    """Load and validate BM25 outside the event-loop thread."""
    return await run_in_thread(
        load_validated_bm25_artifact,
        artifact,
        expected_checksum=expected_checksum,
        format_version=format_version,
        expected_document_count=expected_document_count,
        k=k,
    )


class HybridRetriever:
    """
    Bounded reciprocal-rank fusion over optional dense and BM25 runtimes.
    """
    def __init__(
        self,
        *,
        dense_retriever,
        bm25_retriever,
        bm25_weight: float,
        dense_k: int,
        bm25_k: int,
        final_top_k: int,
    ) -> None:
        if isinstance(bm25_weight, bool) or not isinstance(
            bm25_weight,
            (int, float),
        ):
            raise ValueError("bm25_weight must be a number")
        if not math.isfinite(bm25_weight) or not 0.0 <= bm25_weight <= 1.0:
            raise ValueError("bm25_weight must be between 0.0 and 1.0")
        self.dense_k = _require_positive_k(dense_k, "dense_k")
        self.bm25_k = _require_positive_k(bm25_k, "bm25_k")
        self.final_top_k = _require_positive_k(final_top_k, "final_top_k")
        if self.final_top_k > max(self.dense_k, self.bm25_k):
            raise ValueError("final_top_k must be <= max(dense_k, bm25_k)")
        if bm25_weight < 1.0 and dense_retriever is None:
            raise ValueError("An active dense retriever is required")
        if bm25_weight > 0.0 and bm25_retriever is None:
            raise ValueError("An active BM25 retriever is required")

        self.dense_retriever = dense_retriever
        self.bm25_retriever = bm25_retriever
        self.bm25_weight = float(bm25_weight)

    @staticmethod
    def _ranked_documents(
        documents: Sequence[Document],
        limit: int,
    ) -> dict[int, tuple[int, Document]]:
        ranked: dict[int, tuple[int, Document]] = {}
        for rank, document in enumerate(documents[:limit], start=1):
            chunk_id = _document_chunk_id(document)
            ranked.setdefault(chunk_id, (rank, document))
        return ranked

    def invoke(self, query: str, config=None, **kwargs) -> list[Document]:
        """Retrieve active candidates and fuse them without an RRF constant."""
        dense_ranked: dict[int, tuple[int, Document]] = {}
        bm25_ranked: dict[int, tuple[int, Document]] = {}
        if self.bm25_weight < 1.0:
            dense_ranked = self._ranked_documents(
                self.dense_retriever.invoke(query, config=config, **kwargs),
                self.dense_k,
            )
        if self.bm25_weight > 0.0:
            bm25_ranked = self._ranked_documents(
                self.bm25_retriever.invoke(query, config=config, **kwargs),
                self.bm25_k,
            )

        fused: list[tuple[float, int, Document]] = []
        for chunk_id in dense_ranked.keys() | bm25_ranked.keys():
            dense_entry = dense_ranked.get(chunk_id)
            bm25_entry = bm25_ranked.get(chunk_id)
            dense_rank = dense_entry[0] if dense_entry else None
            bm25_rank = bm25_entry[0] if bm25_entry else None
            if self.bm25_weight == 0.0:
                score = 1.0 / dense_rank
            elif self.bm25_weight == 1.0:
                score = 1.0 / bm25_rank
            else:
                score = 0.0
                if dense_rank is not None:
                    score += (1.0 - self.bm25_weight) / dense_rank
                if bm25_rank is not None:
                    score += self.bm25_weight / bm25_rank

            source = dense_entry[1] if dense_entry else bm25_entry[1]
            metadata = dict(source.metadata)
            metadata.update(
                {
                    "dense_rank": dense_rank,
                    "bm25_rank": bm25_rank,
                    "fused_score": score,
                }
            )
            fused.append(
                (
                    score,
                    chunk_id,
                    Document(
                        page_content=source.page_content,
                        metadata=metadata,
                    ),
                )
            )

        fused.sort(key=lambda item: (-item[0], item[1]))
        return [document for _, _, document in fused[: self.final_top_k]]

    async def ainvoke(self, query: str, config=None, **kwargs) -> list[Document]:
        """Run synchronous child retrievers outside the event-loop thread."""
        return await asyncio.to_thread(self.invoke, query, config, **kwargs)


def make_hybrid_retriever(
    *,
    dense_retriever=None,
    bm25_retriever=None,
    bm25_weight: float = 0.5,
    dense_k: int = 4,
    bm25_k: int = 4,
    final_top_k: int = 4,
) -> HybridRetriever:
    """Create a deterministic, top-k bounded hybrid retriever."""
    return HybridRetriever(
        dense_retriever=dense_retriever,
        bm25_retriever=bm25_retriever,
        bm25_weight=bm25_weight,
        dense_k=dense_k,
        bm25_k=bm25_k,
        final_top_k=final_top_k,
    )


def make_graph_retriever(graph_index, k: int = 3):
    """Create a retriever from a llama-index graph index."""
    retriever = graph_index.as_retriever(
        include_text=True,
        similarity_top_k=k,
    )
    return retriever
