from collections.abc import Sequence
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# local imports
from models.corpus_indices import CorpusIndex
from models.document_chunks import DocumentChunk
from models.indexed_chunks import IndexedChunk
from repositories.helpers import commit_and_refresh, commit_delete
from schemas.indexed_chunks_schemas import (
    IndexedChunkCreate,
    IndexedChunkCreateMany,
    IndexedChunkUpdate,
    IndexedChunkVectorRefsCreate,
)


async def get_indexed_chunk(
    corpus_index_id: int,
    document_chunk_id: int,
    session: AsyncSession,
) -> IndexedChunk | None:
    """
    Get an indexed chunk by corpus index ID and document chunk ID.
        Args:
            corpus_index_id: The ID of the corpus index.
            document_chunk_id: The ID of the document chunk.
            session: The database session.
        Returns:
            The IndexedChunk instance if found, otherwise None.
    """
    result = await session.exec(
        select(IndexedChunk).where(
            IndexedChunk.corpus_index_id == corpus_index_id,
            IndexedChunk.document_chunk_id == document_chunk_id,
        )
    )
    return result.first()


async def get_indexed_chunks_by_corpus_index_id(
    corpus_index_id: int,
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
) -> list[IndexedChunk]:
    """
    Get indexed chunks by corpus index ID.
        Args:
            corpus_index_id: The ID of the corpus index.
            session: The database session.
            skip: The number of records to skip.
            limit: The maximum number of records to return.
        Returns:
            A list of IndexedChunk instances.
    """
    result = await session.exec(
        select(IndexedChunk)
        .where(IndexedChunk.corpus_index_id == corpus_index_id)
        .order_by(IndexedChunk.document_chunk_id)
        .offset(skip)
        .limit(limit)
    )
    return list(result.all())


async def get_indexed_chunks_by_document_chunk_id(
    document_chunk_id: int,
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
) -> list[IndexedChunk]:
    """
    Get indexed chunks by document chunk ID.
        Args:
            document_chunk_id: The ID of the document chunk.
            session: The database session.
            skip: The number of records to skip.
            limit: The maximum number of records to return.
        Returns:
            A list of IndexedChunk instances.
    """
    result = await session.exec(
        select(IndexedChunk)
        .where(IndexedChunk.document_chunk_id == document_chunk_id)
        .order_by(IndexedChunk.corpus_index_id)
        .offset(skip)
        .limit(limit)
    )
    return list(result.all())


async def ensure_corpus_index_exists(
    corpus_index_id: int,
    session: AsyncSession,
) -> None:
    """
    Ensure that a corpus index exists.
        Args:
            corpus_index_id: The ID of the corpus index.
            session: The database session.
        Raises:
            ValueError: If the corpus index does not exist.
    """
    if await session.get(CorpusIndex, corpus_index_id) is None:
        raise ValueError("Corpus index not found")


async def ensure_document_chunk_exists(
    document_chunk_id: int,
    session: AsyncSession,
) -> None:
    """
    Ensure that a document chunk exists.
        Args:
            document_chunk_id: The ID of the document chunk.
            session: The database session.
        Raises:
            ValueError: If the document chunk does not exist.
    """
    if await session.get(DocumentChunk, document_chunk_id) is None:
        raise ValueError("Document chunk not found")


async def ensure_indexed_chunk_available(
    corpus_index_id: int,
    document_chunk_id: int,
    session: AsyncSession,
) -> None:
    """
    Ensure that an indexed chunk is available.
        Args:
            corpus_index_id: The ID of the corpus index.
            document_chunk_id: The ID of the document chunk.
            session: The database session.
        Raises:
            ValueError: If the indexed chunk already exists.
    """
    existing_indexed_chunk = await get_indexed_chunk(
        corpus_index_id,
        document_chunk_id,
        session,
    )
    if existing_indexed_chunk is not None:
        raise ValueError("Indexed chunk already exists")


async def list_indexed_chunks(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    corpus_index_id: int | None = None,
    document_chunk_id: int | None = None,
    has_external_vector_id: bool | None = None,
) -> list[IndexedChunk]:
    """
    List indexed chunks with optional filters.
        Args:
            session: The database session.
            skip: The number of records to skip.
            limit: The maximum number of records to return.
            corpus_index_id: Optional ID of the corpus index to filter by.
            document_chunk_id: Optional ID of the document chunk to filter by.
            has_external_vector_id: Optional flag to filter by presence of 
                external vector ID.
        Returns:
            A list of IndexedChunk instances.
    """
    statement = select(IndexedChunk)

    if corpus_index_id is not None:
        statement = statement.where(IndexedChunk.corpus_index_id == corpus_index_id)
    if document_chunk_id is not None:
        statement = statement.where(IndexedChunk.document_chunk_id == document_chunk_id)
    if has_external_vector_id is not None:
        if has_external_vector_id:
            statement = statement.where(IndexedChunk.external_vector_id.is_not(None))
        else:
            statement = statement.where(IndexedChunk.external_vector_id.is_(None))

    statement = (
        statement
        .order_by(IndexedChunk.corpus_index_id, IndexedChunk.document_chunk_id)
        .offset(skip)
        .limit(limit)
    )
    result = await session.exec(statement)
    return list(result.all())


async def create_indexed_chunk(
    indexed_chunk_in: IndexedChunkCreate,
    session: AsyncSession,
) -> IndexedChunk:
    """
    Create a new indexed chunk.
        Args:
            indexed_chunk_in: The IndexedChunkCreate instance containing the 
                data for the new indexed chunk.
            session: The database session.
        Returns:
            The created IndexedChunk instance.
    """
    await ensure_corpus_index_exists(indexed_chunk_in.corpus_index_id, session)
    await ensure_document_chunk_exists(indexed_chunk_in.document_chunk_id, session)
    await ensure_indexed_chunk_available(
        indexed_chunk_in.corpus_index_id,
        indexed_chunk_in.document_chunk_id,
        session,
    )
    indexed_chunk = IndexedChunk(**indexed_chunk_in.model_dump())
    return await commit_and_refresh(session, indexed_chunk)


async def update_indexed_chunk(
    indexed_chunk: IndexedChunk,
    indexed_chunk_in: IndexedChunkUpdate,
    session: AsyncSession,
) -> IndexedChunk:
    """
    Update an existing indexed chunk.
        Args:
            indexed_chunk: The IndexedChunk instance to update.
            indexed_chunk_in: The IndexedChunkUpdate instance containing the 
                updated data.
            session: The database session.
        Returns:
            The updated IndexedChunk instance.
    """
    update_data = indexed_chunk_in.model_dump(exclude_unset=True)

    if "external_vector_id" in update_data:
        indexed_chunk.external_vector_id = update_data["external_vector_id"]

    return await commit_and_refresh(session, indexed_chunk)


def ensure_indexed_chunk_deletable(indexed_chunk: IndexedChunk) -> None:
    """
    Ensure that an indexed chunk can be deleted.
        Args:
            indexed_chunk: The IndexedChunk instance to check.
        Raises:
            ValueError: If the indexed chunk has an external vector ID.
    """
    if indexed_chunk.external_vector_id is not None:
        raise ValueError("Cannot delete indexed chunk with an external vector id")


async def delete_indexed_chunk(
    indexed_chunk: IndexedChunk,
    session: AsyncSession,
) -> None:
    """
    Delete an indexed chunk from the database.
        Args:
            indexed_chunk: The IndexedChunk instance to be deleted.
            session: The database session.
        Returns:
            None
        Raises:
            ValueError: If the indexed chunk cannot be deleted.
    """
    ensure_indexed_chunk_deletable(indexed_chunk)
    await commit_delete(session, indexed_chunk)


def _normalize_indexed_chunks(
    indexed_chunks_in: IndexedChunkCreateMany | Sequence[IndexedChunkCreate],
) -> list[IndexedChunkCreate]:
    """
    Convert the input indexed chunks to a list of IndexedChunkCreate instances.
    Args:
        indexed_chunks_in: The input indexed chunks, which can be either an
            IndexedChunkCreateMany instance or a sequence of 
            IndexedChunkCreate instances.
    Returns:
        A list of IndexedChunkCreate instances.
    """
    if isinstance(indexed_chunks_in, IndexedChunkCreateMany):
        return indexed_chunks_in.indexed_chunks

    return list(indexed_chunks_in)


def _indexed_chunk_key(indexed_chunk_in: IndexedChunkCreate) -> tuple[int, int]:
    """
    Generate a unique key for an indexed chunk based on its corpus index ID 
    and document chunk ID.
        Args:
            indexed_chunk_in: The IndexedChunkCreate instance.
        Returns:
            A tuple containing the corpus index ID and document chunk ID.
    """
    return (
        indexed_chunk_in.corpus_index_id,
        indexed_chunk_in.document_chunk_id,
    )


def ensure_no_duplicate_indexed_chunks_in_payload(
    indexed_chunks_in: Sequence[IndexedChunkCreate],
) -> None:
    """
    Ensure that there are no duplicate indexed chunks in the payload.
        Args:
            indexed_chunks_in: A sequence of IndexedChunkCreate instances.
        Raises:
            ValueError: If there are duplicate indexed chunks in the payload.
    """
    seen_keys: set[tuple[int, int]] = set()
    for indexed_chunk_in in indexed_chunks_in:
        indexed_chunk_key = _indexed_chunk_key(indexed_chunk_in)
        if indexed_chunk_key in seen_keys:
            raise ValueError("Duplicate indexed chunk in payload")
        seen_keys.add(indexed_chunk_key)


async def _ensure_parent_records_exist(
    indexed_chunks_in: Sequence[IndexedChunkCreate],
    session: AsyncSession,
) -> None:
    """
    Ensure that the parent records for the indexed chunks exist.
        Args:
            indexed_chunks_in: A sequence of IndexedChunkCreate instances.
            session: The database session.
        Raises:
            ValueError: If any of the parent records do not exist.
    """
    corpus_index_ids = {indexed_chunk_in.corpus_index_id for indexed_chunk_in in indexed_chunks_in}
    document_chunk_ids = {indexed_chunk_in.document_chunk_id for indexed_chunk_in in indexed_chunks_in}

    for corpus_index_id in corpus_index_ids:
        await ensure_corpus_index_exists(corpus_index_id, session)
    for document_chunk_id in document_chunk_ids:
        await ensure_document_chunk_exists(document_chunk_id, session)


async def ensure_no_duplicate_indexed_chunks_in_db(
    indexed_chunks_in: Sequence[IndexedChunkCreate],
    session: AsyncSession,
) -> None:
    """
    Ensure that there are no duplicate indexed chunks in the database.
        Args:
            indexed_chunks_in: A sequence of IndexedChunkCreate instances.
            session: The database session.
        Raises:
            ValueError: If there are duplicate indexed chunks in the database.
    """
    for indexed_chunk_in in indexed_chunks_in:
        await ensure_indexed_chunk_available(
            indexed_chunk_in.corpus_index_id,
            indexed_chunk_in.document_chunk_id,
            session,
        )


async def bulk_create_indexed_chunks(
    indexed_chunks_in: IndexedChunkCreateMany | list[IndexedChunkCreate],
    session: AsyncSession,
) -> list[IndexedChunk]:
    """
    Bulk create indexed chunks in the database.
        Args:
            indexed_chunks_in: A sequence of IndexedChunkCreate instances or 
                an IndexedChunkCreateMany instance.
            session: The database session.
        Returns:
            A list of created IndexedChunk instances.
        Raises:
            ValueError: If there are duplicate indexed chunks in the payload or database.
    """
    indexed_chunk_inputs = _normalize_indexed_chunks(indexed_chunks_in)
    if not indexed_chunk_inputs:
        return []

    await _ensure_parent_records_exist(indexed_chunk_inputs, session)
    ensure_no_duplicate_indexed_chunks_in_payload(indexed_chunk_inputs)
    await ensure_no_duplicate_indexed_chunks_in_db(indexed_chunk_inputs, session)

    indexed_chunks = [
        IndexedChunk(**indexed_chunk_in.model_dump())
        for indexed_chunk_in in indexed_chunk_inputs
    ]

    try:
        for indexed_chunk in indexed_chunks:
            session.add(indexed_chunk)

        await session.commit()
        for indexed_chunk in indexed_chunks:
            await session.refresh(indexed_chunk)
        return indexed_chunks
    except Exception:
        await session.rollback()
        raise


def ensure_no_duplicate_vector_refs_in_payload(
    vector_refs_in: IndexedChunkVectorRefsCreate,
) -> None:
    """
    Ensure that there are no duplicate vector references in the payload.
        Args:
            vector_refs_in: The IndexedChunkVectorRefsCreate instance 
                containing the vector references.
        Raises:
            ValueError: If there are duplicate document chunk IDs in the payload.
    """
    seen_document_chunk_ids: set[int] = set()
    for vector_ref in vector_refs_in.chunks:
        if vector_ref.document_chunk_id in seen_document_chunk_ids:
            raise ValueError("Duplicate document chunk id in vector refs payload")
        seen_document_chunk_ids.add(vector_ref.document_chunk_id)


async def update_indexed_chunk_vector_refs(
    vector_refs_in: IndexedChunkVectorRefsCreate,
    session: AsyncSession,
) -> list[IndexedChunk]:
    """
    Update the vector references for indexed chunks in the database.
        Args:
            vector_refs_in: The IndexedChunkVectorRefsCreate instance 
                containing the vector references.
            session: The database session.
        Returns:
            A list of updated IndexedChunk instances.
        Raises:
            ValueError: If any of the indexed chunks are not found.
    """
    if not vector_refs_in.chunks:
        return []

    await ensure_corpus_index_exists(vector_refs_in.corpus_index_id, session)
    ensure_no_duplicate_vector_refs_in_payload(vector_refs_in)

    indexed_chunks: list[IndexedChunk] = []
    for vector_ref in vector_refs_in.chunks:
        indexed_chunk = await get_indexed_chunk(
            vector_refs_in.corpus_index_id,
            vector_ref.document_chunk_id,
            session,
        )
        if indexed_chunk is None:
            raise ValueError("Indexed chunk not found")

        indexed_chunk.external_vector_id = vector_ref.external_vector_id
        indexed_chunks.append(indexed_chunk)

    try:
        for indexed_chunk in indexed_chunks:
            session.add(indexed_chunk)

        await session.commit()
        for indexed_chunk in indexed_chunks:
            await session.refresh(indexed_chunk)
        return indexed_chunks
    except Exception:
        await session.rollback()
        raise


def ensure_indexed_chunks_deletable(indexed_chunks: Sequence[IndexedChunk]) -> None:
    """
    Ensure that a sequence of indexed chunks can be deleted.
        Args:
            indexed_chunks: A sequence of IndexedChunk instances.
        Raises:
            ValueError: If any of the indexed chunks cannot be deleted.
    """
    for indexed_chunk in indexed_chunks:
        ensure_indexed_chunk_deletable(indexed_chunk)


async def delete_indexed_chunks_by_corpus_index_id(
    corpus_index_id: int,
    session: AsyncSession,
) -> int:
    """
    Delete indexed chunks by corpus index ID.
        Args:
            corpus_index_id: The ID of the corpus index.
            session: The database session.
        Returns:
            The number of deleted indexed chunks.
        Raises:
            ValueError: If the corpus index does not exist or any of the 
            indexed chunks cannot be deleted.
    """
    await ensure_corpus_index_exists(corpus_index_id, session)
    result = await session.exec(
        select(IndexedChunk)
        .where(IndexedChunk.corpus_index_id == corpus_index_id)
        .order_by(IndexedChunk.document_chunk_id)
    )
    indexed_chunks = list(result.all())
    ensure_indexed_chunks_deletable(indexed_chunks)

    try:
        for indexed_chunk in indexed_chunks:
            await session.delete(indexed_chunk)

        await session.commit()
        return len(indexed_chunks)
    except Exception:
        await session.rollback()
        raise


async def delete_indexed_chunks_by_document_chunk_id(
    document_chunk_id: int,
    session: AsyncSession,
) -> int:
    """
    Delete indexed chunks by document chunk ID.
        Args:
            document_chunk_id: The ID of the document chunk.
            session: The database session.
        Returns:
            The number of deleted indexed chunks.
        Raises:
            ValueError: If the document chunk does not exist or any of the 
            indexed chunks cannot be deleted.
    """
    await ensure_document_chunk_exists(document_chunk_id, session)
    result = await session.exec(
        select(IndexedChunk)
        .where(IndexedChunk.document_chunk_id == document_chunk_id)
        .order_by(IndexedChunk.corpus_index_id)
    )
    indexed_chunks = list(result.all())
    ensure_indexed_chunks_deletable(indexed_chunks)

    try:
        for indexed_chunk in indexed_chunks:
            await session.delete(indexed_chunk)

        await session.commit()
        return len(indexed_chunks)
    except Exception:
        await session.rollback()
        raise