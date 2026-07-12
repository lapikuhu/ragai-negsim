from collections.abc import Sequence
from sqlalchemy.orm import selectinload
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

# local imports
from app.models.chunking_profiles import ChunkingProfile
from app.models.document_chunks import DocumentChunk
from app.models.indexed_chunks import IndexedChunk
from app.models.raw_documents import CorpusRawDocumentLink
from app.models.raw_documents import RawDocument
from app.repositories.helpers import commit_and_refresh, commit_delete, utc_now
from app.schemas.document_chunks_schemas import (
    DocumentChunkCreate,
    DocumentChunkIndexedChunkRead,
    DocumentChunkReadWithIds,
    DocumentChunkReadWithIndexedChunks,
    DocumentChunkUpdate,
)

async def get_document_chunk_by_id(
    chunk_id: int,
    session: AsyncSession,
) -> DocumentChunk | None:
    """
    Get a document chunk by its ID.
        Args:
            chunk_id: The ID of the document chunk.
            session: The database session.
        Returns:
            The DocumentChunk instance if found, otherwise None.
    """
    return await session.get(DocumentChunk, chunk_id)


async def get_document_chunks_by_raw_document_id(
    raw_document_id: int,
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
) -> list[DocumentChunk]:
    """
    Get document chunks by raw document ID.
        Args:
            raw_document_id: The ID of the raw document.
            session: The database session.
            skip: The number of records to skip.
            limit: The maximum number of records to return.
        Returns:
            A list of DocumentChunk instances.
    """
    result = await session.exec(
        select(DocumentChunk)
        .where(DocumentChunk.raw_document_id == raw_document_id)
        .order_by(DocumentChunk.chunk_index)
        .offset(skip)
        .limit(limit)
    )
    return list(result.all())


async def get_document_chunks_by_chunking_profile_id(
    chunking_profile_id: int,
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
) -> list[DocumentChunk]:
    """
    Get document chunks by chunking profile ID.
        Args:
            chunking_profile_id: The ID of the chunking profile.
            session: The database session.
            skip: The number of records to skip.
            limit: The maximum number of records to return.
        Returns:
            A list of DocumentChunk instances.
    """
    result = await session.exec(
        select(DocumentChunk)
        .where(DocumentChunk.chunking_profile_id == chunking_profile_id)
        .order_by(DocumentChunk.raw_document_id, DocumentChunk.chunk_index)
        .offset(skip)
        .limit(limit)
    )
    return list(result.all())


async def list_document_chunks_for_job(
    indexing_job_id: int,
    session: AsyncSession,
) -> list[DocumentChunk]:
    """
    List document chunks for a specific indexing job.
        Args:
            indexing_job_id: The ID of the indexing job.
            session: The database session.
        Returns:
            A list of DocumentChunk instances.
    """
    result = await session.exec(
        select(DocumentChunk)
        .where(DocumentChunk.indexing_job_id == indexing_job_id)
        .order_by(DocumentChunk.raw_document_id, DocumentChunk.chunk_index)
    )
    return list(result.all())


async def ensure_raw_document_exists(
    raw_document_id: int,
    session: AsyncSession,
) -> None:
    """
    Ensure that a raw document exists.
        Args:
            raw_document_id: The ID of the raw document.
            session: The database session.
        Raises:
            ValueError: If the raw document does not exist.
    """
    if await session.get(RawDocument, raw_document_id) is None:
        raise ValueError("Raw document not found")


async def ensure_chunking_profile_exists(
    chunking_profile_id: int,
    session: AsyncSession,
) -> None:
    """
    Ensure that a chunking profile exists.
        Args:
            chunking_profile_id: The ID of the chunking profile.
            session: The database session.
        Raises:
            ValueError: If the chunking profile does not exist.
    """
    if await session.get(ChunkingProfile, chunking_profile_id) is None:
        raise ValueError("Chunking profile not found")


async def get_document_chunk_by_position(
    raw_document_id: int,
    chunking_profile_id: int,
    chunk_index: int,
    session: AsyncSession,
    indexing_job_id: int | None = None,
) -> DocumentChunk | None:
    """
    Get a document chunk by its position.
        Args:
            raw_document_id: The ID of the raw document.
            chunking_profile_id: The ID of the chunking profile.
            chunk_index: The index of the chunk.
            session: The database session.
        Returns:
            The DocumentChunk instance if found, otherwise None.
    """
    statement = select(DocumentChunk).where(
        DocumentChunk.raw_document_id == raw_document_id,
        DocumentChunk.chunking_profile_id == chunking_profile_id,
        DocumentChunk.chunk_index == chunk_index,
    )
    if indexing_job_id is None:
        statement = statement.where(DocumentChunk.indexing_job_id.is_(None))
    else:
        statement = statement.where(DocumentChunk.indexing_job_id == indexing_job_id)

    result = await session.exec(statement)
    return result.first()


async def ensure_document_chunk_position_available(
    raw_document_id: int,
    chunking_profile_id: int,
    chunk_index: int,
    session: AsyncSession,
    exclude_chunk_id: int | None = None,
    indexing_job_id: int | None = None,
) -> None:
    """
    Ensure that a document chunk position is available.
        Args:
            raw_document_id: The ID of the raw document.
            chunking_profile_id: The ID of the chunking profile.
            chunk_index: The index of the chunk.
            session: The database session.
            exclude_chunk_id: The ID of the chunk to exclude from the check.
        Raises:
            ValueError: If the document chunk position is already taken.
    """
    existing_chunk = await get_document_chunk_by_position(
        raw_document_id,
        chunking_profile_id,
        chunk_index,
        session,
        indexing_job_id=indexing_job_id,
    )
    if existing_chunk is None:
        return

    if exclude_chunk_id is not None and existing_chunk.id == exclude_chunk_id:
        return

    raise ValueError("Document chunk position already exists")


async def document_chunk_has_indexed_chunks(
    chunk_id: int,
    session: AsyncSession,
) -> bool:
    """
    Check if a document chunk has any associated indexed chunks.
        Args:
            chunk_id: The ID of the document chunk.
            session: The database session.
        Returns:
            True if the document chunk has indexed chunks, False otherwise.
    """
    result = await session.exec(
        select(IndexedChunk.document_chunk_id)
        .where(IndexedChunk.document_chunk_id == chunk_id)
        .limit(1)
    )
    return result.first() is not None


async def get_document_chunk_corpus_index_ids(
    chunk_id: int,
    session: AsyncSession,
) -> list[int]:
    """
    Get the corpus index IDs associated with a document chunk.
        Args:
            chunk_id: The ID of the document chunk.
            session: The database session.
        Returns:
            A list of corpus index IDs.
    """
    result = await session.exec(
        select(IndexedChunk.corpus_index_id).where(IndexedChunk.document_chunk_id == chunk_id)
    )
    return [corpus_index_id for corpus_index_id in result.all() if corpus_index_id is not None]


async def get_document_chunk_indexed_chunks(
    chunk_id: int,
    session: AsyncSession,
) -> list[DocumentChunkIndexedChunkRead]:
    """
    Get the indexed chunks associated with a document chunk.
        Args:
            chunk_id: The ID of the document chunk.
            session: The database session.
        Returns:
            A list of DocumentChunkIndexedChunkRead instances.
    """
    result = await session.exec(
        select(IndexedChunk).where(IndexedChunk.document_chunk_id == chunk_id)
    )
    return [
        DocumentChunkIndexedChunkRead(
            corpus_index_id=indexed_chunk.corpus_index_id,
            external_vector_id=indexed_chunk.external_vector_id,
            created_at=indexed_chunk.created_at,
        )
        for indexed_chunk in result.all()
    ]


async def list_document_chunks(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    raw_document_id: int | None = None,
    chunking_profile_id: int | None = None,
    has_indexed_chunks: bool | None = None,
) -> list[DocumentChunk]:
    """
    List document chunks with optional filters.
        Args:
            session: The database session.
            skip: The number of records to skip.
            limit: The maximum number of records to return.
            raw_document_id: The ID of the raw document to filter by.
            chunking_profile_id: The ID of the chunking profile to filter by.
            has_indexed_chunks: Whether to filter by chunks that have indexed chunks.
        Returns:
            A list of DocumentChunk instances.
    """
    statement = _apply_document_chunk_filters(
        select(DocumentChunk).options(
            selectinload(DocumentChunk.raw_document),
            selectinload(DocumentChunk.chunking_profile),
        ),
        raw_document_id=raw_document_id,
        chunking_profile_id=chunking_profile_id,
        has_indexed_chunks=has_indexed_chunks,
    )

    statement = (
        statement
        .order_by(
            DocumentChunk.raw_document_id,
            DocumentChunk.chunking_profile_id,
            DocumentChunk.chunk_index,
        )
        .offset(skip)
        .limit(limit)
    )
    result = await session.exec(statement)
    return list(result.all())


def _apply_document_chunk_filters(
    statement,
    raw_document_id: int | None = None,
    chunking_profile_id: int | None = None,
    has_indexed_chunks: bool | None = None,
):
    """
    Apply filters to a SQLAlchemy statement for querying document chunks.
        Args:
            statement: The SQLAlchemy statement to apply filters to.
            raw_document_id: Optional filter for raw document ID.
            chunking_profile_id: Optional filter for chunking profile ID.
            has_indexed_chunks: Optional filter for whether the chunk has 
                indexed chunks.
        Returns:
            The modified SQLAlchemy statement with the applied filters.
    """
    if raw_document_id is not None:
        statement = statement.where(DocumentChunk.raw_document_id == raw_document_id)
    if chunking_profile_id is not None:
        statement = statement.where(DocumentChunk.chunking_profile_id == chunking_profile_id)
    if has_indexed_chunks is not None:
        indexed_chunk_subquery = select(IndexedChunk.document_chunk_id).distinct()
        if has_indexed_chunks:
            statement = statement.where(DocumentChunk.id.in_(indexed_chunk_subquery))
        else:
            statement = statement.where(DocumentChunk.id.not_in(indexed_chunk_subquery))
    return statement


async def count_document_chunks(
    session: AsyncSession,
    raw_document_id: int | None = None,
    chunking_profile_id: int | None = None,
    has_indexed_chunks: bool | None = None,
) -> int:
    """
    Get the count of document chunks with optional filters.
        Args:
            session: The database session.
            raw_document_id: Optional filter for raw document ID.
            chunking_profile_id: Optional filter for chunking profile ID.
            has_indexed_chunks: Optional filter for whether the chunk has 
                indexed chunks.
        Returns:
            The count of document chunks matching the filters.
    """
    statement = _apply_document_chunk_filters(
        select(func.count()).select_from(DocumentChunk),
        raw_document_id=raw_document_id,
        chunking_profile_id=chunking_profile_id,
        has_indexed_chunks=has_indexed_chunks,
    )
    result = await session.exec(statement)
    return result.one()


async def list_corpus_document_chunks_for_profile(
    corpus_id: int,
    chunking_profile_id: int,
    session: AsyncSession,
) -> list[DocumentChunk]:
    """
    List chunks linked to a corpus for a specific chunking profile.
    Args:
        corpus_id (int): The ID of the corpus.
        chunking_profile_id (int): The ID of the chunking profile.
        session (AsyncSession): The database session.
    Returns:
        list[DocumentChunk]: A list of DocumentChunk instances associated 
        with the corpus and chunking profile.
    """
    result = await session.exec(
        select(DocumentChunk)
        .join(
            CorpusRawDocumentLink,
            DocumentChunk.raw_document_id == CorpusRawDocumentLink.raw_document_id,
        )
        .where(
            CorpusRawDocumentLink.corpus_id == corpus_id,
            DocumentChunk.chunking_profile_id == chunking_profile_id,
        )
        .order_by(DocumentChunk.raw_document_id, DocumentChunk.chunk_index)
    )
    return list(result.all())


async def list_document_chunks_for_corpus_index(
    corpus_index_id: int,
    session: AsyncSession,
) -> list[DocumentChunk]:
    """
    Return the exact persisted chunks associated with a corpus index.
    Args:
        corpus_index_id (int): The ID of the corpus index.
        session (AsyncSession): The database session.
    Returns:
        list[DocumentChunk]: A list of DocumentChunk instances associated 
        with the corpus index.
    """
    result = await session.exec(
        select(DocumentChunk)
        .options(selectinload(DocumentChunk.raw_document))
        .join(
            IndexedChunk,
            IndexedChunk.document_chunk_id == DocumentChunk.id,
        )
        .where(IndexedChunk.corpus_index_id == corpus_index_id)
        .order_by(DocumentChunk.raw_document_id, DocumentChunk.chunk_index)
    )
    return list(result.all())


async def to_document_chunk_read_with_ids(
    chunk: DocumentChunk,
    session: AsyncSession,
) -> DocumentChunkReadWithIds:
    """
    Convert a DocumentChunk instance to a DocumentChunkReadWithIds instance.
        Args:
            chunk: The DocumentChunk instance.
            session: The database session.
        Returns:
            A DocumentChunkReadWithIds instance.
    """
    if chunk.id is None:
        raise ValueError("Document chunk must be persisted before relationship ids can be loaded")

    return DocumentChunkReadWithIds(
        **chunk.model_dump(exclude={"content"}),
        corpus_index_ids=await get_document_chunk_corpus_index_ids(chunk.id, session),
    )


async def to_document_chunk_read_with_indexed_chunks(
    chunk: DocumentChunk,
    session: AsyncSession,
) -> DocumentChunkReadWithIndexedChunks:
    """
    Convert a DocumentChunk instance to a DocumentChunkReadWithIndexedChunks 
    instance.
        Args:
            chunk: The DocumentChunk instance.
            session: The database session.
        Returns:
            A DocumentChunkReadWithIndexedChunks instance.
    """
    if chunk.id is None:
        raise ValueError("Document chunk must be persisted before indexed chunks can be loaded")

    return DocumentChunkReadWithIndexedChunks(
        **chunk.model_dump(exclude={"content"}),
        indexed_chunks=await get_document_chunk_indexed_chunks(chunk.id, session),
    )


async def create_document_chunk(
    chunk_in: DocumentChunkCreate,
    session: AsyncSession,
) -> DocumentChunk:
    """
    Create a new DocumentChunk instance.
        Args:
            chunk_in: The DocumentChunkCreate instance.
            session: The database session.
        Returns:
            The created DocumentChunk instance.
    """
    await ensure_raw_document_exists(chunk_in.raw_document_id, session)
    await ensure_chunking_profile_exists(chunk_in.chunking_profile_id, session)
    await ensure_document_chunk_position_available(
        chunk_in.raw_document_id,
        chunk_in.chunking_profile_id,
        chunk_in.chunk_index,
        session,
        indexing_job_id=chunk_in.indexing_job_id,
    )
    chunk = DocumentChunk(**chunk_in.model_dump())
    return await commit_and_refresh(session, chunk)


async def update_document_chunk(
    chunk: DocumentChunk,
    chunk_in: DocumentChunkUpdate,
    session: AsyncSession,
) -> DocumentChunk:
    """
    Update an existing DocumentChunk instance.
        Args:
            chunk: The DocumentChunk instance to update.
            chunk_in: The DocumentChunkUpdate instance containing the 
                update data.
            session: The database session.
        Returns:
            The updated DocumentChunk instance.
    """
    if chunk.id is None:
        raise ValueError("Document chunk must be persisted before it can be updated")

    update_data = chunk_in.model_dump(exclude_unset=True)

    if "chunk_index" in update_data and update_data["chunk_index"] is not None:
        await ensure_document_chunk_position_available(
            chunk.raw_document_id,
            chunk.chunking_profile_id,
            update_data["chunk_index"],
            session,
            exclude_chunk_id=chunk.id,
            indexing_job_id=chunk.indexing_job_id,
        )

    if "content" in update_data and update_data["content"] is not None:
        if await document_chunk_has_indexed_chunks(chunk.id, session):
            raise ValueError("Cannot update content for an indexed document chunk")

    for field_name, value in update_data.items():
        setattr(chunk, field_name, value)

    chunk.last_updated = utc_now()
    return await commit_and_refresh(session, chunk)


async def ensure_document_chunk_deletable(
    chunk: DocumentChunk,
    session: AsyncSession,
) -> None:
    """
    Ensure that a document chunk can be deleted.
        Args:
            chunk: The DocumentChunk instance to check.
            session: The database session.
        Returns:
            None
        Raises:
            ValueError: If the document chunk cannot be deleted.
    """
    if chunk.id is None:
        raise ValueError("Document chunk must be persisted before it can be deleted")

    if await document_chunk_has_indexed_chunks(chunk.id, session):
        raise ValueError("Cannot delete document chunk with existing indexed chunks")


async def delete_document_chunk(
    chunk: DocumentChunk,
    session: AsyncSession,
) -> None:
    """
    Delete a document chunk.
        Args:
            chunk: The DocumentChunk instance to delete.
            session: The database session.
        Returns:
            None
        Raises:
            ValueError: If the document chunk cannot be deleted.
    """
    await ensure_document_chunk_deletable(chunk, session)
    await commit_delete(session, chunk)


def _chunk_position_key(chunk_in: DocumentChunkCreate) -> tuple[int | None, int, int, int]:
    # TODO: Check functionality.
    """
    Generate a unique key for a document chunk based on its position.
        Args:
            chunk_in: The DocumentChunkCreate instance.
        Returns:
            A tuple representing the unique position key.
    """
    return (
        chunk_in.indexing_job_id,
        chunk_in.raw_document_id,
        chunk_in.chunking_profile_id,
        chunk_in.chunk_index,
    )


async def _ensure_parent_records_exist(
    chunks_in: Sequence[DocumentChunkCreate],
    session: AsyncSession,
) -> None:
    """
    Ensure that the parent records for the given document chunks exist.
        Args:
            chunks_in: A sequence of DocumentChunkCreate instances.
            session: The database session.
        Returns:
            None
        Raises:
            ValueError: If any parent record does not exist.
    """
    raw_document_ids = {chunk_in.raw_document_id for chunk_in in chunks_in}
    chunking_profile_ids = {chunk_in.chunking_profile_id for chunk_in in chunks_in}

    for raw_document_id in raw_document_ids:
        await ensure_raw_document_exists(raw_document_id, session)
    for chunking_profile_id in chunking_profile_ids:
        await ensure_chunking_profile_exists(chunking_profile_id, session)


def ensure_no_duplicate_positions_in_payload(chunks_in: Sequence[DocumentChunkCreate]) -> None:
    """
    Ensure that there are no duplicate positions in the given payload.
        Args:
            chunks_in: A sequence of DocumentChunkCreate instances.
        Returns:
            None
        Raises:
            ValueError: If any duplicate position is found in the payload.
    """
    seen_positions: set[tuple[int, int, int]] = set()
    for chunk_in in chunks_in:
        position_key = _chunk_position_key(chunk_in)
        if position_key in seen_positions:
            raise ValueError("Duplicate document chunk position in payload")
        seen_positions.add(position_key)


async def ensure_no_duplicate_positions_in_db(
    chunks_in: Sequence[DocumentChunkCreate],
    session: AsyncSession,
) -> None:
    """
    Ensure that there are no duplicate positions in the database for the given 
    document chunks.
        Args:
            chunks_in: A sequence of DocumentChunkCreate instances.
            session: The database session.
        Returns:
            None
        Raises:
            ValueError: If any duplicate position is found in the database.
    """
    for chunk_in in chunks_in:
        await ensure_document_chunk_position_available(
            chunk_in.raw_document_id,
            chunk_in.chunking_profile_id,
            chunk_in.chunk_index,
            session,
            indexing_job_id=chunk_in.indexing_job_id,
        )


async def bulk_create_document_chunks(
    chunks_in: list[DocumentChunkCreate],
    session: AsyncSession,
) -> list[DocumentChunk]:
    """
    Bulk create document chunks.
        Args:
            chunks_in: A list of DocumentChunkCreate instances.
            session: The database session.
        Returns:
            A list of created DocumentChunk instances.
        Raises:
            ValueError: If any validation fails.
    """
    if not chunks_in:
        return []

    await _ensure_parent_records_exist(chunks_in, session)
    ensure_no_duplicate_positions_in_payload(chunks_in)
    await ensure_no_duplicate_positions_in_db(chunks_in, session)

    chunks = [DocumentChunk(**chunk_in.model_dump()) for chunk_in in chunks_in]

    try:
        for chunk in chunks:
            session.add(chunk)

        await session.commit()
        for chunk in chunks:
            await session.refresh(chunk)
        return chunks
    except Exception:
        await session.rollback()
        raise


async def delete_document_chunks_by_raw_document_id(
    raw_document_id: int,
    session: AsyncSession,
) -> int:
    """
    Delete document chunks by raw document ID.
        Args:
            raw_document_id: The ID of the raw document.
            session: The database session.
        Returns:
            The number of deleted document chunks.
        Raises:
            ValueError: If the raw document does not exist.
    """
    await ensure_raw_document_exists(raw_document_id, session)

    result = await session.exec(
        select(DocumentChunk)
        .where(DocumentChunk.raw_document_id == raw_document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = list(result.all())

    for chunk in chunks:
        await ensure_document_chunk_deletable(chunk, session)

    try:
        for chunk in chunks:
            await session.delete(chunk)

        await session.commit()
        return len(chunks)
    except Exception:
        await session.rollback()
        raise
