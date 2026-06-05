from datetime import datetime, timezone

from app.db.db import AsyncSessionLocal
from app.services.helpers import _persisted_id
from langchain_core.documents import Document
from app.models.chunking_profiles import ChunkingProfile
from app.models.corpus import Corpus
from app.models.corpus_indices import CorpusIndex
from app.models.vector_stores import VectorStore
from app.repositories import (
    chunking_profiles_repo,
    corpus_indices_repo,
    corpus_repo,
    vector_stores_repo,
)
from app.repositories.document_chunks_repo import list_corpus_document_chunks_for_profile
from app.repositories.indexed_chunks_repo import bulk_create_indexed_chunks
from app.schemas.corpus_indices_schemas import (
    CorpusIndexBuildComplete,
    CorpusIndexCreate,
)
from app.schemas.embeddings_schemas import (
    CorpusEmbeddingBuildQueued,
    CorpusEmbeddingBuildRequest,
    CorpusEmbeddingBuildResult,
    IndexedChunkBuildRef,
)
from app.schemas.indexed_chunks_schemas import IndexedChunkCreate
from sqlmodel.ext.asyncio.session import AsyncSession

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
    build_error: str,
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
        await corpus_indices_repo.mark_corpus_index_failed(
            index,
            build_error,
            session,
        )
    except Exception:
        await session.rollback()


def _short_error(exc: Exception, max_length: int = 500) -> str:
    """
    Helper function to convert an exception to a short error message string.
    Args:
        exc (Exception): The exception to convert.
        max_length (int): The maximum length of the error message string. 
            Defaults to 500.
    Returns:
        str: A string representation of the error message, truncated to 
        the maximum length if necessary.
    """
    message = str(exc).strip() or exc.__class__.__name__
    if len(message) <= max_length:
        return message
    return f"{message[: max_length - 3]}..."


async def _build_existing_corpus_index(
    index: CorpusIndex,
    corpus: Corpus,
    chunking_profile: ChunkingProfile,
    vector_store: VectorStore,
    session: AsyncSession,
) -> CorpusEmbeddingBuildResult:
    """
    Build an existing corpus index.
    Args:
        index (CorpusIndex): The corpus index to build.
        corpus (Corpus): The corpus associated with the index.
        chunking_profile (ChunkingProfile): The chunking profile to use.
        vector_store (VectorStore): The vector store to use.
        session (AsyncSession): The database session to use.
    Returns:
        CorpusEmbeddingBuildResult: The result of the build process.
    """
    corpus_id = _persisted_id(corpus.id, "Corpus")
    chunking_profile_id = _persisted_id(chunking_profile.id, "Chunking profile")
    vector_store_id = _persisted_id(vector_store.id, "Vector store")
    corpus_index_id = _persisted_id(index.id, "Corpus index")

    from app.airag.embeddings.embeddings import choose_embedding_model

    embedding_model, embedding_metadata = choose_embedding_model(index.embedding_model)
    embedding_dimensions = embedding_metadata["dimensionality"]
    vector_namespace = _vector_namespace(corpus_index_id, index.vector_namespace)

    chunks = await list_corpus_document_chunks_for_profile(
        corpus_id=corpus_id,
        chunking_profile_id=chunking_profile_id,
        session=session,
    )
    if not chunks:
        raise ValueError("No document chunks found for this corpus and chunking profile. Chunk the corpus first.")

    documents, vector_refs = _to_vector_documents(
        chunks=chunks,
        corpus_id=corpus_id,
        corpus_index_id=corpus_index_id,
        chunking_profile_id=chunking_profile_id,
    )
    vector_ids = [vector_ref.external_vector_id for vector_ref in vector_refs]

    from app.airag.vector_stores.vector_stores import store_docs_to_vector_store

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

    return CorpusEmbeddingBuildResult(
        corpus_id=corpus_id,
        corpus_index_id=corpus_index_id,
        vector_store_id=vector_store_id,
        chunking_profile_id=chunking_profile_id,
        embedding_model=index.embedding_model,
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


async def queue_corpus_embedding_build_srvc(
    corpus: Corpus,
    chunking_profile: ChunkingProfile,
    vector_store: VectorStore,
    build_in: CorpusEmbeddingBuildRequest,
    session: AsyncSession,
) -> CorpusEmbeddingBuildQueued:
    """
    Queue a corpus embedding build by creating a corpus index with status 
    "building". The actual embedding build work will be performed 
    asynchronously in the background.
    Args:
        corpus (Corpus): The corpus for which to build embeddings.
        chunking_profile (ChunkingProfile): The chunking profile to use.
        vector_store (VectorStore): The vector store to use.
        build_in (CorpusEmbeddingBuildRequest): The build request details.
        session (AsyncSession): The database session.
    Returns:
        CorpusEmbeddingBuildQueued: The details of the queued build.
    Raises:
        ValueError: If no document chunks are found for the given corpus and
        chunking profile.
    """
    corpus_id = _persisted_id(corpus.id, "Corpus")
    chunking_profile_id = _persisted_id(chunking_profile.id, "Chunking profile")
    vector_store_id = _persisted_id(vector_store.id, "Vector store")

    from app.airag.embeddings.embeddings import choose_embedding_model

    _embedding_model, embedding_metadata = choose_embedding_model(build_in.embedding_model)
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
            status="building",
            embedding_model=build_in.embedding_model,
            embedding_dimensions=embedding_dimensions,
            vector_namespace=build_in.vector_namespace,
        ),
        session,
    )
    corpus_index_id = _persisted_id(index.id, "Corpus index")
    vector_namespace = _vector_namespace(corpus_index_id, build_in.vector_namespace)
    index = await corpus_indices_repo.set_corpus_index_build_metadata(
        index,
        vector_namespace,
        session,
    )

    return CorpusEmbeddingBuildQueued(
        corpus_id=corpus_id,
        corpus_index_id=corpus_index_id,
        vector_store_id=vector_store_id,
        chunking_profile_id=chunking_profile_id,
        embedding_model=build_in.embedding_model,
        embedding_dimensions=embedding_dimensions,
        vector_namespace=vector_namespace,
        status=index.status,
    )


async def _load_build_records(
    corpus_index_id: int,
    session: AsyncSession,
) -> tuple[CorpusIndex, Corpus, ChunkingProfile, VectorStore]:
    """
    Load the build records for a given corpus index.
    Args:
        corpus_index_id: The ID of the corpus index.
        session: The database session.
    Returns:
        A tuple containing the corpus index, corpus, chunking profile, and vector store.
    Raises:
        ValueError: If any of the required records are not found or if the corpus index
        is not in the "building" status.
    """
    index = await corpus_indices_repo.get_corpus_index_by_id(corpus_index_id, session)
    if index is None:
        raise ValueError("Corpus index not found")
    if index.status != "building":
        raise ValueError("Corpus index must be building before queued build can run")

    corpus = await corpus_repo.get_corpus_by_id(index.corpus_id, session)
    if corpus is None:
        raise ValueError("Corpus not found")

    chunking_profile = await chunking_profiles_repo.get_chunking_profile_by_id(
        index.chunking_profile_id,
        session,
    )
    if chunking_profile is None:
        raise ValueError("Chunking profile not found")

    vector_store = await vector_stores_repo.get_vector_store_by_id(
        index.vector_store_id,
        session,
    )
    if vector_store is None:
        raise ValueError("Vector store not found")

    return index, corpus, chunking_profile, vector_store


async def run_queued_corpus_embedding_build_srvc(
    corpus_index_id: int,
) -> CorpusEmbeddingBuildResult:
    """
    Run a queued corpus embedding build. This is the service that performs 
    the actual embedding build work for a corpus index that has been queued 
    with status "building". It loads the necessary records, builds the corpus 
    index, and updates the index status accordingly. If any errors occur 
    during the build process, it marks the corpus index as failed with the 
    error message.
    Args:
        corpus_index_id: The ID of the corpus index to build.
    Returns:
        CorpusEmbeddingBuildResult: The result of the corpus embedding build.
    Raises:
        Exception: If any error occurs during the build process. The corpus 
        index will be marked as failed with the error message.
    """
    async with AsyncSessionLocal() as session:
        index: CorpusIndex | None = None
        try:
            index, corpus, chunking_profile, vector_store = await _load_build_records(
                corpus_index_id,
                session,
            )
            return await _build_existing_corpus_index(
                index=index,
                corpus=corpus,
                chunking_profile=chunking_profile,
                vector_store=vector_store,
                session=session,
            )
        except Exception as exc:
            if index is None:
                index = await corpus_indices_repo.get_corpus_index_by_id(
                    corpus_index_id,
                    session,
                )
            if index is not None and index.status == "building":
                await session.rollback()
                await corpus_indices_repo.mark_corpus_index_failed(
                    index,
                    _short_error(exc),
                    session,
                )
            raise


async def build_corpus_embeddings_srvc(
    corpus: Corpus,
    chunking_profile: ChunkingProfile,
    vector_store: VectorStore,
    build_in: CorpusEmbeddingBuildRequest,
    session: AsyncSession,
) -> CorpusEmbeddingBuildResult:
    """
    Creates and synchronously builds a corpus index for manual debugging.
    The alpha API path queues the same build work in the background.
    Args:
        corpus (Corpus): The corpus for which to build embeddings.
        chunking_profile (ChunkingProfile): The chunking profile to use.
        vector_store (VectorStore): The vector store to use.
        build_in (CorpusEmbeddingBuildRequest): The build request details.
        session (AsyncSession): The database session.
    Returns:
        CorpusEmbeddingBuildResult: The result of the build process.
    Raises:
        Exception: If any error occurs during the build process. The corpus 
        index will be marked as failed with the error message.
    """
    queued = await queue_corpus_embedding_build_srvc(
        corpus=corpus,
        chunking_profile=chunking_profile,
        vector_store=vector_store,
        build_in=build_in,
        session=session,
    )
    index = await corpus_indices_repo.get_corpus_index_by_id(
        queued.corpus_index_id,
        session,
    )
    if index is None:
        raise ValueError("Corpus index not found")

    try:
        return await _build_existing_corpus_index(
            index=index,
            corpus=corpus,
            chunking_profile=chunking_profile,
            vector_store=vector_store,
            session=session,
        )
    except Exception as exc:
        await _mark_index_failed(index, session, _short_error(exc))
        raise
