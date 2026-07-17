"""Chunk synthetic evaluation documents using persisted chunking profiles."""
from __future__ import annotations
from collections.abc import Sequence
from langchain_core.documents import Document

# local imports
from app.airag.chunking import normalize_chunking_profile_config
from app.airag.chunking.chunkers import (
    chunk_document_list_hybrid,
    chunk_document_list_recursive,
    chunk_document_list_semantic,
)


def prepare_evaluation_chunks(
    documents: Sequence[Document], chunking_snapshot: dict,
) -> list[Document]:
    """
    Chunk evaluation documents and attach source offsets for scoring.
    Args:
        documents: A sequence of Document instances to be chunked.
        chunking_snapshot: The chunking snapshot configuration.
    Returns:
        A list of Document instances with attached source offsets.
    Raises:
        ValueError: If any chunk cannot be aligned to its source document.
    """
    strategy = chunking_snapshot.get("strategy")
    config = normalize_chunking_profile_config(strategy, chunking_snapshot.get("config"))
    source_documents = list(documents)

    if strategy == "recursive":
        chunks = chunk_document_list_recursive(source_documents, **config)
    elif strategy == "semantic":
        # TODO: Make the chunk-boundary embedding model configurable and snapshot it.
        chunks = chunk_document_list_semantic(source_documents, **config)
    elif strategy == "hybrid":
        # TODO: Make the chunk-boundary embedding model configurable and snapshot it.
        chunks = chunk_document_list_hybrid(source_documents, **config)
    else:  # normalize_chunking_profile_config raises first; kept for type narrowing.
        raise ValueError(f"Unsupported chunking strategy: {strategy}")

    source_by_id = {
        document.metadata.get("eval_document_id"): document.page_content
        for document in source_documents
    }
    next_search_start: dict[str, int] = {}
    chunk_indices: dict[str, int] = {}
    aligned: list[Document] = []
    for chunk in chunks:
        metadata = dict(chunk.metadata)
        document_id = metadata.get("eval_document_id")
        source = source_by_id.get(document_id)
        if not isinstance(document_id, str) or source is None:
            raise ValueError("Evaluation chunks must preserve eval_document_id metadata")
        start = source.find(chunk.page_content, next_search_start.get(document_id, 0))
        if start < 0:
            raise ValueError(
                f"Evaluation chunk for {document_id} cannot be aligned to its source document"
            )
        end = start + len(chunk.page_content)
        metadata["start_index"] = start
        metadata["end_index"] = end
        metadata["chunk_index"] = chunk_indices.get(document_id, 0)
        next_search_start[document_id] = start + 1
        chunk_indices[document_id] = metadata["chunk_index"] + 1
        aligned.append(Document(page_content=chunk.page_content, metadata=metadata))
    return aligned
