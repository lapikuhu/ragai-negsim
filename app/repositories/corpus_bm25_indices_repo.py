"""Persistence operations for BM25 artifacts independent of dense corpus indexes."""

from hashlib import sha256

from sqlalchemy import delete, update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.corpus_bm25_indices import CorpusBm25Index
from app.repositories.helpers import commit_and_refresh, utc_now
from app.schemas.corpus_bm25_indices_schemas import (
    CorpusBm25IndexCreate,
    CorpusBm25IndexMetadata,
)


ALLOWED_CORPUS_BM25_INDEX_STATUSES = {
    "created",
    "building",
    "built",
    "failed",
    "cancelled",
    "retired",
}
ALLOWED_CORPUS_BM25_INDEX_STATUS_TRANSITIONS = {
    "created": {"building", "failed", "cancelled", "retired"},
    "building": {"built", "failed", "cancelled", "retired"},
    "built": {"retired"},
    "failed": {"retired"},
    "cancelled": {"retired"},
    "retired": set(),
}


def document_chunk_ids_checksum(document_chunk_ids: list[int]) -> str:
    """
    Return the canonical checksum for a BM25 artifact's chunk set.
    Args:
        document_chunk_ids: The list of document chunk IDs that were used 
        to build the BM25 artifact
    Returns:
        A SHA256 checksum of the canonical serialization of the document 
        chunk IDs.
    """
    serialized_ids = ",".join(str(chunk_id) for chunk_id in sorted(document_chunk_ids))
    return sha256(serialized_ids.encode("utf-8")).hexdigest()


def ensure_corpus_bm25_index_status(status: str) -> None:
    """
    Ensure the given status is a valid corpus BM25 index status.

    Args:
        status: The status to validate.
    Returns:
        None
    Raises:
        ValueError: If the status is not allowed.
    """
    if status not in ALLOWED_CORPUS_BM25_INDEX_STATUSES:
        raise ValueError("Invalid corpus BM25 index status")


def ensure_corpus_bm25_index_status_transition(
    current_status: str,
    next_status: str,
) -> None:
    """
    Ensure the transition from the current status to the next status is valid.

    Args:
        current_status: The current status of the corpus BM25 index.
        next_status: The desired next status of the corpus BM25 index.
    Returns:
        None
    Raises:
        ValueError: If the transition is not allowed.
    """
    ensure_corpus_bm25_index_status(current_status)
    ensure_corpus_bm25_index_status(next_status)
    if next_status not in ALLOWED_CORPUS_BM25_INDEX_STATUS_TRANSITIONS[current_status]:
        raise ValueError("Invalid corpus BM25 index status transition")


def _corpus_bm25_index_metadata_statement():
    """
    Select only API-safe artifact metadata not artifact bytes.
    Args:
        None
    Returns:
        A SQLAlchemy select statement for corpus BM25 index metadata.
    """
    return select(
        CorpusBm25Index.id,
        CorpusBm25Index.name,
        CorpusBm25Index.corpus_id,
        CorpusBm25Index.chunking_profile_id,
        CorpusBm25Index.status,
        CorpusBm25Index.format_version,
        CorpusBm25Index.document_count,
        CorpusBm25Index.document_chunk_ids_checksum,
        CorpusBm25Index.compressed_artifact_checksum,
        CorpusBm25Index.built_at,
        CorpusBm25Index.created_at,
        CorpusBm25Index.last_updated,
        CorpusBm25Index.build_error,
        CorpusBm25Index.created_by_full_corpus_index_pipe_job_id,
        CorpusBm25Index.created_by_bm25_build_job_id,
    )


def _corpus_bm25_index_metadata_columns():
    """
    Return the columns for corpus BM25 index metadata.
    Args:
        None
    Returns:
        A tuple of SQLAlchemy columns for corpus BM25 index metadata.
    """
    return (
        CorpusBm25Index.id,
        CorpusBm25Index.name,
        CorpusBm25Index.corpus_id,
        CorpusBm25Index.chunking_profile_id,
        CorpusBm25Index.status,
        CorpusBm25Index.format_version,
        CorpusBm25Index.document_count,
        CorpusBm25Index.document_chunk_ids_checksum,
        CorpusBm25Index.compressed_artifact_checksum,
        CorpusBm25Index.built_at,
        CorpusBm25Index.created_at,
        CorpusBm25Index.last_updated,
        CorpusBm25Index.build_error,
        CorpusBm25Index.created_by_full_corpus_index_pipe_job_id,
        CorpusBm25Index.created_by_bm25_build_job_id,
    )


def _to_metadata(row) -> CorpusBm25IndexMetadata:
    """
    Helper function to map a SQLAlchemy row to CorpusBm25IndexMetadata.
    Args:
        row: A SQLAlchemy row object containing corpus BM25 index metadata.
    Returns:
        A CorpusBm25IndexMetadata object constructed from the row data.
    """
    return CorpusBm25IndexMetadata(**dict(row._mapping))


async def get_corpus_bm25_index_metadata_by_id(
    index_id: int,
    session: AsyncSession,
) -> CorpusBm25IndexMetadata | None:
    """
    Get corpus BM25 index metadata by ID.

    Args:
        index_id: The ID of the corpus BM25 index.
        session: The SQLAlchemy AsyncSession to use for the query.
    Returns:
        A CorpusBm25IndexMetadata object if found, otherwise None.
    """
    result = await session.exec(
        _corpus_bm25_index_metadata_statement().where(CorpusBm25Index.id == index_id)
    )
    row = result.first()
    return None if row is None else _to_metadata(row)


async def list_corpus_bm25_index_metadata(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 20,
    corpus_id: int | None = None,
    chunking_profile_id: int | None = None,
    status: str | None = None,
) -> list[CorpusBm25IndexMetadata]:
    """
    List corpus BM25 index metadata with optional filters.

    Args:
        session: The SQLAlchemy AsyncSession to use for the query.
        skip: The number of records to skip.
        limit: The maximum number of records to return.
        corpus_id: Optional corpus ID to filter by.
        chunking_profile_id: Optional chunking profile ID to filter by.
        status: Optional status to filter by.
    Returns:
        A list of CorpusBm25IndexMetadata objects matching the filters.
    """
    statement = _corpus_bm25_index_metadata_statement()
    if corpus_id is not None:
        statement = statement.where(CorpusBm25Index.corpus_id == corpus_id)
    if chunking_profile_id is not None:
        statement = statement.where(CorpusBm25Index.chunking_profile_id == chunking_profile_id)
    if status is not None:
        ensure_corpus_bm25_index_status(status)
        statement = statement.where(CorpusBm25Index.status == status)
    statement = statement.order_by(CorpusBm25Index.id).offset(skip).limit(limit)
    result = await session.exec(statement)
    return [_to_metadata(row) for row in result.all()]


async def get_corpus_bm25_index_artifact_by_id(
    index_id: int,
    session: AsyncSession,
) -> bytes | None:
    """
    Get the artifact bytes of a corpus BM25 index by ID.

    Args:
        index_id: The ID of the corpus BM25 index.
        session: The SQLAlchemy AsyncSession to use for the query.
    Returns:
        The artifact bytes if found, otherwise None.
    """
    result = await session.exec(
        select(CorpusBm25Index.artifact).where(CorpusBm25Index.id == index_id)
    )
    return result.first()


def prepare_corpus_bm25_index(
    index_in: CorpusBm25IndexCreate,
) -> CorpusBm25Index:
    """
    Prepare a CorpusBm25Index instance from the given input data.

    Args:
        index_in: The input data for creating the corpus BM25 index.
    Returns:
        A CorpusBm25Index instance populated with the input data.
    """
    index_data = index_in.model_dump(exclude={"document_chunk_ids"})
    return CorpusBm25Index(
        **index_data,
        document_count=len(index_in.document_chunk_ids),
        document_chunk_ids_checksum=document_chunk_ids_checksum(
            index_in.document_chunk_ids
        ),
    )


async def create_corpus_bm25_index(
    index_in: CorpusBm25IndexCreate,
    session: AsyncSession,
    *,
    prepared_index: CorpusBm25Index | None = None,
) -> CorpusBm25Index:
    """
    Create a new corpus BM25 index in the database from the prepared
    CorpusBm25Index instance or the input data.

    Args:
        index_in: The input data for creating the corpus BM25 index.
        session: The SQLAlchemy AsyncSession to use for the operation.
        prepared_index: An optional pre-prepared CorpusBm25Index instance.
    Returns:
        The created CorpusBm25Index instance.
    """
    index = prepared_index or prepare_corpus_bm25_index(index_in)
    return await commit_and_refresh(session, index)


def _corpus_bm25_index_id(index_id: int) -> int:
    """
    Get the persisted corpus BM25 index ID.

    Args:
        index_id: The ID of the corpus BM25 index.
    Returns:
        The persisted corpus BM25 index ID.
    Raises:
        ValueError: If the index ID is not an integer.
    """
    if not isinstance(index_id, int):
        raise ValueError("Corpus BM25 index must be persisted before transition")
    return index_id


def _allowed_current_statuses(next_status: str) -> tuple[str, ...]:
    """
    Get the allowed current statuses for a given next status.

    Args:
        next_status: The next status to check.
    Returns:
        A tuple of allowed current statuses.
    """
    return tuple(
        current_status
        for current_status, allowed_next_statuses in ALLOWED_CORPUS_BM25_INDEX_STATUS_TRANSITIONS.items()
        if next_status in allowed_next_statuses
    )


async def _conditional_lifecycle_update(
    index_id: int,
    status: str,
    values: dict,
    session: AsyncSession,
) -> CorpusBm25IndexMetadata:
    """
    Update the status of a corpus BM25 index if the current status allows it.

    Args:
        index_id: The ID of the corpus BM25 index to update.
        status: The new status to set.
        values: Additional values to update on the index.
        session: The database session to use for the operation.
    Returns:
        The updated CorpusBm25IndexMetadata object.
    Raises:
        ValueError: If the index does not exist or the status transition is 
        invalid.
    """
    ensure_corpus_bm25_index_status(status)
    persisted_id = _corpus_bm25_index_id(index_id)
    statement = (
        update(CorpusBm25Index)
        .where(
            CorpusBm25Index.id == persisted_id,
            CorpusBm25Index.status.in_(_allowed_current_statuses(status)),
        )
        .values(**values, status=status)
        .returning(*_corpus_bm25_index_metadata_columns())
    )
    try:
        result = await session.exec(statement)
        row = result.one_or_none()
    except Exception:
        await session.rollback()
        raise
    if row is None:
        await session.rollback()
        try:
            metadata = await get_corpus_bm25_index_metadata_by_id(
                persisted_id,
                session,
            )
        finally:
            await session.rollback()
        if metadata is None:
            raise ValueError("Corpus BM25 index not found")
        raise ValueError("Invalid corpus BM25 index status transition")
    try:
        metadata = _to_metadata(row)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return metadata


async def mark_corpus_bm25_index_building(
    index_id: int,
    session: AsyncSession,
) -> CorpusBm25IndexMetadata:
    """
    Mark a corpus BM25 index as "building" if the current status allows it.
    Args:
        index_id: The ID of the corpus BM25 index to update.
        session: The database session to use for the operation.
    Returns:
        The updated CorpusBm25IndexMetadata object.
    """
    return await _conditional_lifecycle_update(
        index_id,
        "building",
        {"last_updated": utc_now()},
        session,
    )


async def mark_corpus_bm25_index_built(
    index_id: int,
    *,
    artifact: bytes,
    document_chunk_ids: list[int],
    session: AsyncSession,
) -> CorpusBm25IndexMetadata:
    """
    Mark a corpus BM25 index as "built" if the current status allows it.
    Args:
        index_id: The ID of the corpus BM25 index to update.
        artifact: The built artifact as bytes.
        document_chunk_ids: The list of document chunk IDs included in 
        the index.
        session: The database session to use for the operation.
    Returns:
        The updated CorpusBm25IndexMetadata object.
    """
    now = utc_now()
    return await _conditional_lifecycle_update(
        index_id,
        "built",
        {
            "artifact": artifact,
            "document_count": len(document_chunk_ids),
            "document_chunk_ids_checksum": document_chunk_ids_checksum(document_chunk_ids),
            "compressed_artifact_checksum": sha256(artifact).hexdigest(),
            "built_at": now,
            "build_error": None,
            "last_updated": now,
        },
        session,
    )


async def mark_corpus_bm25_index_failed(
    index_id: int,
    build_error: str,
    session: AsyncSession,
) -> CorpusBm25IndexMetadata:
    """
    Mark a corpus BM25 index as "failed" if the current status allows it.
    Args:
        index_id: The ID of the corpus BM25 index to update.
        build_error: The error message describing the failure.
        session: The database session to use for the operation.
    Returns:
        The updated CorpusBm25IndexMetadata object.
    """
    return await _conditional_lifecycle_update(
        index_id,
        "failed",
        {"build_error": build_error, "last_updated": utc_now()},
        session,
    )


async def mark_corpus_bm25_index_cancelled(
    index_id: int,
    build_error: str,
    session: AsyncSession,
) -> CorpusBm25IndexMetadata:
    """
    Mark a corpus BM25 index as "cancelled" if the current status allows it.

    Args:
        index_id: The ID of the corpus BM25 index to update.
        build_error: The error message describing the cancellation.
        session: The database session to use for the operation.
    Returns:
        The updated CorpusBm25IndexMetadata object.
    """
    return await _conditional_lifecycle_update(
        index_id,
        "cancelled",
        {"build_error": build_error, "last_updated": utc_now()},
        session,
    )


async def _compensate_corpus_bm25_index_build(
    index_id: int,
    build_error: str,
    *,
    status: str,
    allowed_current_statuses: tuple[str, ...],
    session: AsyncSession,
) -> CorpusBm25IndexMetadata:
    """
    Compensate a corpus BM25 index build failure or cancellation.

    Args:
        index_id: The ID of the corpus BM25 index to update.
        build_error: The error message describing the failure or cancellation.
        status: The status to set ("failed" or "cancelled").
        allowed_current_statuses: A tuple of statuses that are allowed for 
            the transition.
        session: The database session to use for the operation.
    Returns:
        The updated CorpusBm25IndexMetadata object.
    """
    persisted_id = _corpus_bm25_index_id(index_id)
    await session.rollback()
    now = utc_now()
    statement = (
        update(CorpusBm25Index)
        .where(
            CorpusBm25Index.id == persisted_id,
            CorpusBm25Index.status.in_(allowed_current_statuses),
        )
        .values(
            status=status,
            artifact=None,
            compressed_artifact_checksum=None,
            built_at=None,
            build_error=build_error,
            last_updated=now,
        )
        .returning(*_corpus_bm25_index_metadata_columns())
    )
    try:
        result = await session.exec(statement)
        row = result.one_or_none()
    except Exception:
        await session.rollback()
        raise
    if row is None:
        await session.rollback()
        metadata = await get_corpus_bm25_index_metadata_by_id(
            persisted_id,
            session,
        )
        await session.rollback()
        if metadata is None:
            raise ValueError("Corpus BM25 index not found")
        raise ValueError(f"Corpus BM25 index build cannot be marked {status}")
    try:
        metadata = _to_metadata(row)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return metadata


async def cancel_corpus_bm25_index_build(
    index_id: int,
    build_error: str,
    session: AsyncSession,
) -> CorpusBm25IndexMetadata:
    """
    Compensate task cancellation and atomically remove any built artifact.
    This build-only recovery does not make built-to-cancelled an ordinary
    lifecycle transition.

    Args:
        index_id: The ID of the corpus BM25 index to update.
        build_error: The error message describing the cancellation.
        session: The database session to use for the operation.
    """
    return await _compensate_corpus_bm25_index_build(
        index_id,
        build_error,
        status="cancelled",
        allowed_current_statuses=("created", "building", "built", "cancelled"),
        session=session,
    )


async def fail_corpus_bm25_index_build(
    index_id: int,
    build_error: str,
    session: AsyncSession,
) -> CorpusBm25IndexMetadata:
    """
    Compensate an ambiguous build failure and clear any durable artifact.
    This build-only recovery does not make built-to-failed an ordinary
    lifecycle transition.

    Args:
        index_id: The ID of the corpus BM25 index to update.
        build_error: The error message describing the failure.
        session: The database session to use for the operation.
    Returns:
        The updated CorpusBm25IndexMetadata object.
    """
    return await _compensate_corpus_bm25_index_build(
        index_id,
        build_error,
        status="failed",
        allowed_current_statuses=("created", "building", "built", "failed"),
        session=session,
    )


async def mark_corpus_bm25_index_retired(
    index_id: int,
    session: AsyncSession,
) -> CorpusBm25IndexMetadata:
    """
    Mark the corpus BM25 index as retired.

    Args:
        index_id: The ID of the corpus BM25 index to update.
        session: The database session to use for the operation.
    Returns:
        The updated CorpusBm25IndexMetadata object.
    """
    return await _conditional_lifecycle_update(
        index_id,
        "retired",
        {"last_updated": utc_now()},
        session,
    )


async def delete_corpus_bm25_index(
    index_id: int,
    session: AsyncSession,
) -> None:
    """
    Delete the corpus BM25 index.

    Args:
        index_id: The ID of the corpus BM25 index to delete.
        session: The database session to use for the operation.
    Returns:
        None
    Raises:
        ValueError: If the corpus BM25 index is not found.
    """
    persisted_id = _corpus_bm25_index_id(index_id)
    try:
        result = await session.exec(
            delete(CorpusBm25Index)
            .where(CorpusBm25Index.id == persisted_id)
            .returning(CorpusBm25Index.id)
        )
        deleted_id = result.one_or_none()
    except Exception:
        await session.rollback()
        raise
    if deleted_id is None:
        await session.rollback()
        raise ValueError("Corpus BM25 index not found")
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise
