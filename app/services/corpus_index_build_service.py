"""Shared conversion helpers for corpus-index build services."""

from langchain_core.documents import Document

from app.schemas.embeddings_schemas import IndexedChunkBuildRef
from app.services.helpers import _persisted_id


def documents_from_persisted_chunks(
    chunks,
    *,
    corpus_id: int,
    chunking_profile_id: int,
    corpus_index_id: int | None = None,
) -> list[Document]:
    """Convert persisted chunks into LangChain documents with safe provenance."""
    documents: list[Document] = []

    for chunk in chunks:
        document_chunk_id = _persisted_id(chunk.id, "Document chunk")
        metadata = dict(chunk.chunk_metadata or {})
        metadata.update(
            {
                "corpus_id": corpus_id,
                "raw_document_id": chunk.raw_document_id,
                "chunking_profile_id": chunking_profile_id,
                "document_chunk_id": document_chunk_id,
            }
        )
        if corpus_index_id is not None:
            metadata["corpus_index_id"] = corpus_index_id
        documents.append(Document(page_content=chunk.content, metadata=metadata))

    return documents


def to_vector_documents(
    chunks,
    corpus_id: int,
    corpus_index_id: int,
    chunking_profile_id: int,
) -> tuple[list[Document], list[IndexedChunkBuildRef]]:
    """Convert chunks into dense documents and their persisted vector references."""
    documents = documents_from_persisted_chunks(
        chunks,
        corpus_id=corpus_id,
        corpus_index_id=corpus_index_id,
        chunking_profile_id=chunking_profile_id,
    )
    vector_refs = [
        IndexedChunkBuildRef(
            document_chunk_id=document.metadata["document_chunk_id"],
            external_vector_id=(
                f"corpus-index-{corpus_index_id}-chunk-"
                f"{document.metadata['document_chunk_id']}"
            ),
        )
        for document in documents
    ]
    return documents, vector_refs
