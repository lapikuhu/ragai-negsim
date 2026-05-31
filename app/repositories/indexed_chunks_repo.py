from collections.abc import Sequence

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
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


async def get_indexed_chunk(
    corpus_index_id: int,
    document_chunk_id: int,
    session: AsyncSession,
) -> IndexedChunk | None:
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
    if await session.get(CorpusIndex, corpus_index_id) is None:
        raise ValueError("Corpus index not found")


async def ensure_document_chunk_exists(
    document_chunk_id: int,
    session: AsyncSession,
) -> None:
    if await session.get(DocumentChunk, document_chunk_id) is None:
        raise ValueError("Document chunk not found")


async def ensure_indexed_chunk_available(
    corpus_index_id: int,
    document_chunk_id: int,
    session: AsyncSession,
) -> None:
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
    update_data = indexed_chunk_in.model_dump(exclude_unset=True)

    if "external_vector_id" in update_data:
        indexed_chunk.external_vector_id = update_data["external_vector_id"]

    return await commit_and_refresh(session, indexed_chunk)


def ensure_indexed_chunk_deletable(indexed_chunk: IndexedChunk) -> None:
    if indexed_chunk.external_vector_id is not None:
        raise ValueError("Cannot delete indexed chunk with an external vector id")


async def delete_indexed_chunk(
    indexed_chunk: IndexedChunk,
    session: AsyncSession,
) -> None:
    ensure_indexed_chunk_deletable(indexed_chunk)
    await commit_delete(session, indexed_chunk)


def _normalize_indexed_chunks(
    indexed_chunks_in: IndexedChunkCreateMany | Sequence[IndexedChunkCreate],
) -> list[IndexedChunkCreate]:
    if isinstance(indexed_chunks_in, IndexedChunkCreateMany):
        return indexed_chunks_in.indexed_chunks

    return list(indexed_chunks_in)


def _indexed_chunk_key(indexed_chunk_in: IndexedChunkCreate) -> tuple[int, int]:
    return (
        indexed_chunk_in.corpus_index_id,
        indexed_chunk_in.document_chunk_id,
    )


def ensure_no_duplicate_indexed_chunks_in_payload(
    indexed_chunks_in: Sequence[IndexedChunkCreate],
) -> None:
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
    seen_document_chunk_ids: set[int] = set()
    for vector_ref in vector_refs_in.chunks:
        if vector_ref.document_chunk_id in seen_document_chunk_ids:
            raise ValueError("Duplicate document chunk id in vector refs payload")
        seen_document_chunk_ids.add(vector_ref.document_chunk_id)


async def update_indexed_chunk_vector_refs(
    vector_refs_in: IndexedChunkVectorRefsCreate,
    session: AsyncSession,
) -> list[IndexedChunk]:
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
    for indexed_chunk in indexed_chunks:
        ensure_indexed_chunk_deletable(indexed_chunk)


async def delete_indexed_chunks_by_corpus_index_id(
    corpus_index_id: int,
    session: AsyncSession,
) -> int:
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