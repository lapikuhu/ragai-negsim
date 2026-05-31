from collections.abc import Sequence

from models.chunking_profiles import ChunkingProfile
from models.document_chunks import DocumentChunk
from models.indexed_chunks import IndexedChunk
from models.raw_documents import RawDocument
from repositories.helpers import commit_and_refresh, commit_delete, utc_now
from schemas.document_chunks_schemas import (
    DocumentChunkCreate,
    DocumentChunkIndexedChunkRead,
    DocumentChunkReadWithIds,
    DocumentChunkReadWithIndexedChunks,
    DocumentChunkUpdate,
)
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


async def get_document_chunk_by_id(
    chunk_id: int,
    session: AsyncSession,
) -> DocumentChunk | None:
    return await session.get(DocumentChunk, chunk_id)


async def get_document_chunks_by_raw_document_id(
    raw_document_id: int,
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
) -> list[DocumentChunk]:
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
    result = await session.exec(
        select(DocumentChunk)
        .where(DocumentChunk.chunking_profile_id == chunking_profile_id)
        .order_by(DocumentChunk.raw_document_id, DocumentChunk.chunk_index)
        .offset(skip)
        .limit(limit)
    )
    return list(result.all())


async def ensure_raw_document_exists(
    raw_document_id: int,
    session: AsyncSession,
) -> None:
    if await session.get(RawDocument, raw_document_id) is None:
        raise ValueError("Raw document not found")


async def ensure_chunking_profile_exists(
    chunking_profile_id: int,
    session: AsyncSession,
) -> None:
    if await session.get(ChunkingProfile, chunking_profile_id) is None:
        raise ValueError("Chunking profile not found")


async def get_document_chunk_by_position(
    raw_document_id: int,
    chunking_profile_id: int,
    chunk_index: int,
    session: AsyncSession,
) -> DocumentChunk | None:
    result = await session.exec(
        select(DocumentChunk).where(
            DocumentChunk.raw_document_id == raw_document_id,
            DocumentChunk.chunking_profile_id == chunking_profile_id,
            DocumentChunk.chunk_index == chunk_index,
        )
    )
    return result.first()


async def ensure_document_chunk_position_available(
    raw_document_id: int,
    chunking_profile_id: int,
    chunk_index: int,
    session: AsyncSession,
    exclude_chunk_id: int | None = None,
) -> None:
    existing_chunk = await get_document_chunk_by_position(
        raw_document_id,
        chunking_profile_id,
        chunk_index,
        session,
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
    result = await session.exec(
        select(IndexedChunk.corpus_index_id).where(IndexedChunk.document_chunk_id == chunk_id)
    )
    return [corpus_index_id for corpus_index_id in result.all() if corpus_index_id is not None]


async def get_document_chunk_indexed_chunks(
    chunk_id: int,
    session: AsyncSession,
) -> list[DocumentChunkIndexedChunkRead]:
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
    statement = select(DocumentChunk)

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


async def to_document_chunk_read_with_ids(
    chunk: DocumentChunk,
    session: AsyncSession,
) -> DocumentChunkReadWithIds:
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
    await ensure_raw_document_exists(chunk_in.raw_document_id, session)
    await ensure_chunking_profile_exists(chunk_in.chunking_profile_id, session)
    await ensure_document_chunk_position_available(
        chunk_in.raw_document_id,
        chunk_in.chunking_profile_id,
        chunk_in.chunk_index,
        session,
    )
    chunk = DocumentChunk(**chunk_in.model_dump())
    return await commit_and_refresh(session, chunk)


async def update_document_chunk(
    chunk: DocumentChunk,
    chunk_in: DocumentChunkUpdate,
    session: AsyncSession,
) -> DocumentChunk:
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
    if chunk.id is None:
        raise ValueError("Document chunk must be persisted before it can be deleted")

    if await document_chunk_has_indexed_chunks(chunk.id, session):
        raise ValueError("Cannot delete document chunk with existing indexed chunks")


async def delete_document_chunk(
    chunk: DocumentChunk,
    session: AsyncSession,
) -> None:
    await ensure_document_chunk_deletable(chunk, session)
    await commit_delete(session, chunk)


def _chunk_position_key(chunk_in: DocumentChunkCreate) -> tuple[int, int, int]:
    return (
        chunk_in.raw_document_id,
        chunk_in.chunking_profile_id,
        chunk_in.chunk_index,
    )


async def _ensure_parent_records_exist(
    chunks_in: Sequence[DocumentChunkCreate],
    session: AsyncSession,
) -> None:
    raw_document_ids = {chunk_in.raw_document_id for chunk_in in chunks_in}
    chunking_profile_ids = {chunk_in.chunking_profile_id for chunk_in in chunks_in}

    for raw_document_id in raw_document_ids:
        await ensure_raw_document_exists(raw_document_id, session)
    for chunking_profile_id in chunking_profile_ids:
        await ensure_chunking_profile_exists(chunking_profile_id, session)


def ensure_no_duplicate_positions_in_payload(chunks_in: Sequence[DocumentChunkCreate]) -> None:
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
    for chunk_in in chunks_in:
        await ensure_document_chunk_position_available(
            chunk_in.raw_document_id,
            chunk_in.chunking_profile_id,
            chunk_in.chunk_index,
            session,
        )


async def bulk_create_document_chunks(
    chunks_in: list[DocumentChunkCreate],
    session: AsyncSession,
) -> list[DocumentChunk]:
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