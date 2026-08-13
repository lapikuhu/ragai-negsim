"""Build persisted BM25 artifacts independently from dense corpus indexes."""

import asyncio
from collections.abc import Awaitable, Callable
from hashlib import sha256
from typing import TypeVar

from sqlmodel.ext.asyncio.session import AsyncSession

from app.airag.retrieval.retrievers import (
    BM25_ARTIFACT_FORMAT_VERSION,
    build_serialized_bm25_artifact,
    load_validated_bm25_artifact,
)
from app.repositories import corpus_bm25_indices_repo
from app.repositories.document_chunks_repo import list_corpus_document_chunks_for_profile
from app.schemas.corpus_bm25_indices_schemas import (
    CorpusBm25IndexCreate,
    CorpusBm25IndexMetadata,
)
from app.services.corpus_index_build_service import documents_from_persisted_chunks
from app.services.helpers import _persisted_id
from app.services import simulations_service

# Type hint for the generic return type of _await_durable
_T = TypeVar("_T")


async def list_corpus_bm25_indices_srvc(
    *,
    session: AsyncSession,
    skip: int,
    limit: int,
    corpus_id: int | None = None,
    chunking_profile_id: int | None = None,
    status: str | None = None,
) -> list[CorpusBm25IndexMetadata]:
    """
    List BM25 index metadata with optional filtering.
    Args:
        session: The database session to use.
        skip: The number of records to skip.
        limit: The maximum number of records to return.
        corpus_id: Optional corpus ID to filter by.
        chunking_profile_id: Optional chunking profile ID to filter by.
        status: Optional status to filter by.
    Returns:
        A list of CorpusBm25IndexMetadata objects.
    """
    return await corpus_bm25_indices_repo.list_corpus_bm25_index_metadata(
        session,
        skip=skip,
        limit=limit,
        corpus_id=corpus_id,
        chunking_profile_id=chunking_profile_id,
        status=status,
    )

# Helper candidate
def _short_error(exc: BaseException, max_length: int = 500) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    if len(message) <= max_length:
        return message
    return f"{message[: max_length - 3]}..."


def _build_serialize_and_validate_bm25(documents) -> bytes:
    """
    Build a serialized BM25 artifact from the given documents and validate it.
    The artifact is then ready to be persisted in the database.
    Args:
        documents: The documents to build the BM25 artifact from.
    Returns:
        The serialized BM25 artifact as bytes.
    """
    artifact = build_serialized_bm25_artifact(documents)
    load_validated_bm25_artifact(
        artifact,
        expected_checksum=sha256(artifact).hexdigest(),
        format_version=BM25_ARTIFACT_FORMAT_VERSION,
        expected_document_count=len(documents),
    )
    return artifact


async def _await_durable(operation: Awaitable[_T]) -> _T:
    """
    Await an operation while ensuring that cancellation is handled gracefully.
    If the operation is cancelled, it will be allowed to complete, and the
    cancellation will be raised after the operation finishes.
    Args:
        operation: The awaitable operation to execute.
    Returns:
        The result of the operation if it completes successfully.
    Raises:
        asyncio.CancelledError: If the operation is cancelled.
    """
    operation_task = asyncio.ensure_future(operation)
    cancellation: asyncio.CancelledError | None = None

    while not operation_task.done():
        try:
            # Protect the operation from cancellation, but still allow it to 
            #  be cancelled if the operation itself is cancelled.
            result = await asyncio.shield(operation_task)
        except asyncio.CancelledError as exc:
            if cancellation is None:
                cancellation = exc
            continue
        except Exception:
            if cancellation is not None:
                raise cancellation
            raise
        else:
            if cancellation is not None:
                raise cancellation
            return result

    if cancellation is not None:
        try:
            operation_task.result()
        except BaseException:
            pass
        raise cancellation
    return operation_task.result()


async def _mark_build_failed(
    index_id: int,
    build_error: str,
    session: AsyncSession,
) -> None:
    """
    Mark a BM25 index build as failed and clear the associated graph cache.

    Args:
        index_id: The ID of the BM25 index.
        build_error: The error message describing the build failure.
        session: The database session to use.
    Returns:
        None.
    """
    metadata: CorpusBm25IndexMetadata | None = None
    try:
        metadata = await _await_durable(
            corpus_bm25_indices_repo.fail_corpus_bm25_index_build(
                index_id,
                build_error,
                session,
            )
        )
    finally:
        _clear_bm25_graph_cache(index_id, metadata)


async def _mark_build_cancelled(
    index_id: int,
    build_error: str,
    session: AsyncSession,
) -> None:
    """
    Mark a BM25 index build as cancelled and clear the associated graph cache.

    Args:
        index_id: The ID of the BM25 index.
        build_error: The error message describing the build cancellation.
        session: The database session to use.
    Returns:
        None.
    """
    metadata: CorpusBm25IndexMetadata | None = None
    try:
        metadata = await _await_durable(
            corpus_bm25_indices_repo.cancel_corpus_bm25_index_build(
                index_id,
                build_error,
                session,
            )
        )
    finally:
        _clear_bm25_graph_cache(index_id, metadata)


def _clear_bm25_graph_cache(
    index_id: int,
    metadata: CorpusBm25IndexMetadata | None = None,
) -> int:
    """
    Clear the BM25 graph cache for the given index.

    Args:
        index_id: The ID of the BM25 index.
        metadata: The metadata of the BM25 index, if available.
    Returns:
        The result of the cache clearing operation.
    """
    return simulations_service.clear_negotiation_graph_cache_for_bm25_index(
        index_id,
        **(
            {
                "artifact_checksum": metadata.compressed_artifact_checksum,
                "document_chunk_ids_checksum": metadata.document_chunk_ids_checksum,
            }
            if metadata is not None
            else {}
        ),
    )


async def retire_corpus_bm25_index_srvc(
    index: CorpusBm25IndexMetadata,
    session: AsyncSession,
) -> CorpusBm25IndexMetadata:
    """
    Mark a BM25 index as retired and clear the associated graph cache.

    Args:
        index: The metadata of the BM25 index to retire.
        session: The database session to use.
    Returns:
        The retired BM25 index metadata.
    """
    retired = await corpus_bm25_indices_repo.mark_corpus_bm25_index_retired(
        index.id,
        session,
    )
    _clear_bm25_graph_cache(index.id, index)
    return retired


async def delete_corpus_bm25_index_srvc(
    index: CorpusBm25IndexMetadata,
    session: AsyncSession,
) -> None:
    """
    Mark a BM25 index as deleted and clear the associated graph cache.

    Args:
        index: The metadata of the BM25 index to delete.
        session: The database session to use.
    Returns:
        None.
    """
    await corpus_bm25_indices_repo.delete_corpus_bm25_index(index.id, session)
    _clear_bm25_graph_cache(index.id, index)


async def build_corpus_bm25_index_srvc(
    *,
    name: str,
    corpus_id: int,
    chunking_profile_id: int,
    session: AsyncSession,
    expected_document_chunk_ids: list[int] | None = None,
    created_by_bm25_build_job_id: int | None = None,
    on_index_created: Callable[[int], Awaitable[None]] | None = None,
    before_finalize: Callable[[], Awaitable[None]] | None = None,
    run_in_thread: Callable[..., Awaitable[bytes]] = asyncio.to_thread,
) -> CorpusBm25IndexMetadata:
    """
    Create, validate, and atomically persist one BM25 artifact snapshot.

    Args:
        name: The name of the BM25 index.
        corpus_id: The ID of the corpus.
        chunking_profile_id: The ID of the chunking profile.
        session: The database session to use.
        run_in_thread: A callable to run blocking operations in a thread.
        expected_document_chunk_ids: Optional list of expected document 
            chunk IDs to validate against the current set of persisted chunks.
        created_by_bm25_build_job_id: Optional ID of the BM25 build job 
            that created this index.
        on_index_created: Optional callback to invoke when the index is 
            created.
        before_finalize: Optional callback to invoke before finalizing the 
            index build.
    Returns:
        The metadata of the created BM25 index.
    Raises:
        ValueError: If no document chunks are found or if the expected 
        document chunk IDs do not match the current set of persisted chunks.
    """
    # Get the persisted document chunks for the given corpus and chunking profile.
    chunks = await list_corpus_document_chunks_for_profile(
        corpus_id=corpus_id,
        chunking_profile_id=chunking_profile_id,
        session=session,
    )
    if not chunks:
        raise ValueError(
            "No document chunks found for this corpus and chunking profile. "
            "Chunk the corpus first."
        )
    # Get the chunk ids
    document_chunk_ids = [
        _persisted_id(chunk.id, "Document chunk") for chunk in chunks
    ]
    if expected_document_chunk_ids is not None and sorted(document_chunk_ids) != sorted(
        expected_document_chunk_ids
    ):
        raise ValueError(
            "The corpus chunk set changed since the job was queued. "
            "Retry to build the current snapshot."
        )
    # Return the documents from the persisted chunks
    documents = documents_from_persisted_chunks(
        chunks,
        corpus_id=corpus_id,
        chunking_profile_id=chunking_profile_id,
    )

    index_in = CorpusBm25IndexCreate(
        name=name,
        corpus_id=corpus_id,
        chunking_profile_id=chunking_profile_id,
        document_chunk_ids=document_chunk_ids,
        format_version=BM25_ARTIFACT_FORMAT_VERSION,
        created_by_bm25_build_job_id=created_by_bm25_build_job_id,
    )
    prepared_index = corpus_bm25_indices_repo.prepare_corpus_bm25_index(index_in)
    index_id: int | None = None

    async def create_index() -> None:
        """
        Create the BM25 index in the database.

        Returns:
            None.
        """
        nonlocal index_id # Mark index_id as nonlocal to modify it within this nested function
        # TODO: Reuse an existing compatible BM25 artifact instead of rebuilding one for every corpus index.
        index = await corpus_bm25_indices_repo.create_corpus_bm25_index(
            index_in,
            session,
            prepared_index=prepared_index,
        )
        index_id = _persisted_id(index.id, "Corpus BM25 index")
        if on_index_created is not None:
            await on_index_created(index_id)

    def recover_index_id() -> int | None:
        """
        Recover the index ID if it has been set.

        Returns:
            The index ID if available, otherwise None.
        """
        nonlocal index_id # Mark index_id as nonlocal to access it within this nested function
        if index_id is None and isinstance(prepared_index.id, int):
            index_id = prepared_index.id
        return index_id

    try:
        await _await_durable(create_index())
        # Start building the BM25 artifact and mark the index as building
        await _await_durable(
            corpus_bm25_indices_repo.mark_corpus_bm25_index_building(
                index_id,
                session,
            )
        )
        artifact = await run_in_thread(_build_serialize_and_validate_bm25, documents)
        if before_finalize is not None:
            await before_finalize()
        # Mark the index as built and persist the artifact and document chunk ids
        return await _await_durable(
            corpus_bm25_indices_repo.mark_corpus_bm25_index_built(
                index_id,
                artifact=artifact,
                document_chunk_ids=document_chunk_ids,
                session=session,
            )
        )
    # Handle cancellation
    except asyncio.CancelledError as exc:
        if recover_index_id() is None:
            raise
        try:
            await _mark_build_cancelled(index_id, _short_error(exc), session)
        except (asyncio.CancelledError, Exception):
            pass
        raise exc
    # Handle regular exceptions
    except Exception as exc:
        if recover_index_id() is not None:
            try:
                await _mark_build_failed(index_id, _short_error(exc), session)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
        raise


async def build_corpus_bm25_index_from_snapshot_srvc(
    *,
    name: str,
    corpus_id: int,
    chunking_profile_id: int,
    document_chunk_ids: list[int],
    created_by_bm25_build_job_id: int,
    session: AsyncSession,
    on_index_created: Callable[[int], Awaitable[None]] | None = None,
    before_finalize: Callable[[], Awaitable[None]] | None = None,
) -> CorpusBm25IndexMetadata:
    """
    Build BM25 only if the corpus/profile still matches a queued snapshot.
    Args:
        name: The name of the BM25 index to create.
        corpus_id: The ID of the corpus.
        chunking_profile_id: The ID of the chunking profile.
        document_chunk_ids: The list of document chunk IDs to include in 
            the index.
        created_by_bm25_build_job_id: The ID of the BM25 build job that 
            triggered this index creation.
        session: The database session to use.
        on_index_created: Optional callback to invoke when the index is 
            created.
        before_finalize: Optional callback to invoke before finalizing the 
            index build.

    Returns:
        CorpusBm25IndexMetadata: Metadata of the created BM25 index.

    Raises:
        ValueError: If no document chunks are found or if the expected document chunk IDs do not match the current set of persisted chunks.
    """
    return await build_corpus_bm25_index_srvc(
        name=name,
        corpus_id=corpus_id,
        chunking_profile_id=chunking_profile_id,
        expected_document_chunk_ids=document_chunk_ids,
        created_by_bm25_build_job_id=created_by_bm25_build_job_id,
        on_index_created=on_index_created,
        before_finalize=before_finalize,
        session=session,
    )
