from datetime import datetime, timezone

from langchain_core.documents import Document
from models.chunking_profiles import ChunkingProfile
from models.corpus import Corpus
from models.corpus_indices import CorpusIndex
from models.vector_stores import VectorStore
from repositories import corpus_indices_repo
from repositories.document_chunks_repo import list_corpus_document_chunks_for_profile
from repositories.indexed_chunks_repo import bulk_create_indexed_chunks
from schemas.corpus_indices_schemas import (
    CorpusIndexBuildComplete,
    CorpusIndexCreate,
    CorpusIndexStatusUpdate,
)
from schemas.embeddings_schemas import (
    CorpusEmbeddingBuildRequest,
    CorpusEmbeddingBuildResult,
    IndexedChunkBuildRef,
)
from schemas.indexed_chunks_schemas import IndexedChunkCreate
from sqlmodel.ext.asyncio.session import AsyncSession

# Move this to a utils file since it can be used across multiple services
def _persisted_id(value: int | None, label: str) -> int:
    if value is None:
        raise ValueError(f"{label} must be persisted before embedding")
    return value


def _vector_namespace(index_id: int, requested_namespace: str | None) -> str:
    """
    Determine the namespace for the vector store based on the index ID and the
    requested namespace.
    Args:
        index_id (int): The ID of the corpus index.
        requested_namespace (str | None): The requested namespace, if any.
    Returns:
        str: The namespace to use for the vector store.
    """
    if requested_namespace is not None and requested_namespace.strip():
        return requested_namespace
    return f"corpus-index-{index_id}"


def _external_vector_id(corpus_index_id: int, document_chunk_id: int) -> str:
    """
    Generate an external vector ID based on the corpus index ID and document chunk ID.
    Args:
        corpus_index_id (int): The ID of the corpus index.
        document_chunk_id (int): The ID of the document chunk.
    Returns:
        str: The external vector ID.
    """
    return f"corpus-index-{corpus_index_id}-chunk-{document_chunk_id}"


def _to_vector_documents( # CHECK
    chunks,
    corpus_id: int,
    corpus_index_id: int,
    chunking_profile_id: int,
) -> tuple[list[Document], list[IndexedChunkBuildRef]]:
    """
    Convert document chunks into vector store documents and build references.
    Args:
        chunks: The list of document chunks.
        corpus_id (int): The ID of the corpus.
        corpus_index_id (int): The ID of the corpus index.
        chunking_profile_id (int): The ID of the chunking profile.
    Returns:
        tuple[list[Document], list[IndexedChunkBuildRef]]: A tuple containing the list of
        vector store documents and the list of indexed chunk build references.
    """
    documents: list[Document] = []
    vector_refs: list[IndexedChunkBuildRef] = []

    for chunk in chunks:
        document_chunk_id = _persisted_id(chunk.id, "Document chunk")
        external_vector_id = _external_vector_id(corpus_index_id, document_chunk_id)
        metadata = dict(chunk.chunk_metadata or {})
        metadata.update(
            {
                "corpus_id": corpus_id,
                "corpus_index_id": corpus_index_id,
                "raw_document_id": chunk.raw_document_id,
                "chunking_profile_id": chunking_profile_id,
                "document_chunk_id": document_chunk_id,
            }
        )
        documents.append(Document(page_content=chunk.content, metadata=metadata))
        vector_refs.append(
            IndexedChunkBuildRef(
                document_chunk_id=document_chunk_id,
                external_vector_id=external_vector_id,
            )
        )

    return documents, vector_refs


async def _mark_index_failed(
    index: CorpusIndex,
    session: AsyncSession,
) -> None:
    """
    Mark the given corpus index as failed.
    Args:
        index (CorpusIndex): The corpus index to mark as failed.
        session (AsyncSession): The database session to use for the update.
    Returns:
        None
    """
    try:
        await corpus_indices_repo.update_corpus_index_status(
            index,
            CorpusIndexStatusUpdate(status="failed"),
            session,
        )
    except Exception:
        await session.rollback()


async def build_corpus_embeddings_srvc(
    corpus: Corpus,
    chunking_profile: ChunkingProfile,
    vector_store: VectorStore,
    build_in: CorpusEmbeddingBuildRequest,
    session: AsyncSession,
) -> CorpusEmbeddingBuildResult:
    """
    Creates a corpus index for the given corpus and chunking profile, 
    generates embeddings for the document chunks, and stores them in the 
    specified vector store. The corpus index status is updated throughout 
    the process, and any failures are handled gracefully.
    Args:
        corpus (Corpus): The corpus for which to build embeddings.
        chunking_profile (ChunkingProfile): The chunking profile to use for the corpus.
        vector_store (VectorStore): The vector store in which to store the embeddings.
        build_in (CorpusEmbeddingBuildRequest): The build request containing parameters for the embedding process.
        session (AsyncSession): The database session to use for the operations.
    Returns:
        CorpusEmbeddingBuildResult: The result of the embedding build process.
    """
    corpus_id = _persisted_id(corpus.id, "Corpus")
    chunking_profile_id = _persisted_id(chunking_profile.id, "Chunking profile")
    vector_store_id = _persisted_id(vector_store.id, "Vector store")

    from airag.embeddings.embeddings import choose_embedding_model

    embedding_model, embedding_metadata = choose_embedding_model(build_in.embedding_model)
    embedding_dimensions = embedding_metadata["dimensionality"]

    chunks = await list_corpus_document_chunks_for_profile(
        corpus_id=corpus_id,
        chunking_profile_id=chunking_profile_id,
        session=session,
    )
    if not chunks:
        raise ValueError("No document chunks found for this corpus and chunking profile. Chunk the corpus first.")

    index = await corpus_indices_repo.create_corpus_index(
        CorpusIndexCreate(
            name=build_in.name,
            corpus_id=corpus_id,
            vector_store_id=vector_store_id,
            chunking_profile_id=chunking_profile_id,
            status="created",
            embedding_model=build_in.embedding_model,
            embedding_dimensions=embedding_dimensions,
            vector_namespace=build_in.vector_namespace,
        ),
        session,
    )
    corpus_index_id = _persisted_id(index.id, "Corpus index")
    vector_namespace = _vector_namespace(corpus_index_id, build_in.vector_namespace)

    index = await corpus_indices_repo.update_corpus_index_status(
        index,
        CorpusIndexStatusUpdate(status="building"),
        session,
    )

    documents, vector_refs = _to_vector_documents(
        chunks=chunks,
        corpus_id=corpus_id,
        corpus_index_id=corpus_index_id,
        chunking_profile_id=chunking_profile_id,
    )
    vector_ids = [vector_ref.external_vector_id for vector_ref in vector_refs]

    try:
        from airag.vector_stores.vector_stores import store_docs_to_vector_store

        stored_vector_ids = await store_docs_to_vector_store(
            docs=documents,
            embedding_model=embedding_model,
            backend=vector_store.backend,
            ids=vector_ids,
            embedding_dimensions=embedding_dimensions,
            collection_name=vector_store.collection_name,
            path=vector_store.path,
            table_name=vector_store.table_name,
        )

        indexed_chunks_in = [
            IndexedChunkCreate(
                corpus_index_id=corpus_index_id,
                document_chunk_id=vector_ref.document_chunk_id,
                external_vector_id=stored_vector_id,
            )
            for vector_ref, stored_vector_id in zip(vector_refs, stored_vector_ids, strict=True)
        ]
        await bulk_create_indexed_chunks(indexed_chunks_in, session)

        index = await corpus_indices_repo.mark_corpus_index_built(
            index,
            CorpusIndexBuildComplete(
                status="built",
                built_at=datetime.now(timezone.utc),
                embedding_dimensions=embedding_dimensions,
                vector_namespace=vector_namespace,
            ),
            session,
        )
    except Exception:
        await _mark_index_failed(index, session)
        raise

    return CorpusEmbeddingBuildResult(
        corpus_id=corpus_id,
        corpus_index_id=corpus_index_id,
        vector_store_id=vector_store_id,
        chunking_profile_id=chunking_profile_id,
        embedding_model=build_in.embedding_model,
        embedding_dimensions=embedding_dimensions,
        vector_namespace=vector_namespace,
        status=index.status,
        built_at=index.built_at,
        chunks_indexed=len(vector_refs),
        indexed_chunks=vector_refs,
        store_metadata={
            "backend": vector_store.backend,
            "collection_name": vector_store.collection_name,
            "table_name": vector_store.table_name,
            "path": vector_store.path,
        },
    )
