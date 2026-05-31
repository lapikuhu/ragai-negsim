from models.corpus_indices import CorpusIndex
from models.indexed_chunks import IndexedChunk
from repositories.helpers import commit_and_refresh, commit_delete, utc_now
from schemas.corpus_indices_schemas import (
    CorpusIndexBuildComplete,
    CorpusIndexCopy,
    CorpusIndexCreate,
    CorpusIndexIndexedChunkRead,
    CorpusIndexReadWithIds,
    CorpusIndexReadWithIndexedChunks,
    CorpusIndexStatusUpdate,
    CorpusIndexUpdate,
)
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


ALLOWED_CORPUS_INDEX_STATUSES = {"created", "building", "built", "failed", "cancelled"}
ALLOWED_STATUS_TRANSITIONS = {
    "created": {"building", "failed", "cancelled"},
    "building": {"built", "failed", "cancelled"},
    "built": set(),
    "failed": set(),
    "cancelled": set(),
}
BLOCKED_GENERAL_UPDATE_STATUSES = {"building", "built"}


def ensure_corpus_index_status(status: str) -> None:
    if status not in ALLOWED_CORPUS_INDEX_STATUSES:
        raise ValueError("Invalid corpus index status")


def ensure_status_transition(current_status: str, next_status: str) -> None:
    ensure_corpus_index_status(current_status)
    ensure_corpus_index_status(next_status)

    if current_status == next_status:
        return

    if next_status not in ALLOWED_STATUS_TRANSITIONS[current_status]:
        raise ValueError("Invalid corpus index status transition")


def ensure_embedding_model(embedding_model: str | None) -> None:
    if embedding_model is None or not embedding_model.strip():
        raise ValueError("Embedding model must not be blank")


def ensure_embedding_dimensions(embedding_dimensions: int | None) -> None:
    if embedding_dimensions is not None and embedding_dimensions <= 0:
        raise ValueError("Embedding dimensions must be positive")


async def get_corpus_index_by_id(
    index_id: int,
    session: AsyncSession,
) -> CorpusIndex | None:
    return await session.get(CorpusIndex, index_id)


async def get_corpus_index_by_name(
    name: str,
    session: AsyncSession,
) -> CorpusIndex | None:
    result = await session.exec(select(CorpusIndex).where(CorpusIndex.name == name))
    return result.first()


async def ensure_corpus_index_name_available(
    name: str,
    session: AsyncSession,
    exclude_index_id: int | None = None,
) -> None:
    existing_index = await get_corpus_index_by_name(name, session)
    if existing_index is None:
        return

    if exclude_index_id is not None and existing_index.id == exclude_index_id:
        return

    raise ValueError("Corpus index name already exists")


async def has_indexed_chunks(
    corpus_index_id: int,
    session: AsyncSession,
) -> bool:
    result = await session.exec(
        select(IndexedChunk.document_chunk_id)
        .where(IndexedChunk.corpus_index_id == corpus_index_id)
        .limit(1)
    )
    return result.first() is not None


async def get_corpus_index_document_chunk_ids(
    corpus_index_id: int,
    session: AsyncSession,
) -> list[int]:
    result = await session.exec(
        select(IndexedChunk.document_chunk_id).where(
            IndexedChunk.corpus_index_id == corpus_index_id
        )
    )
    return [document_chunk_id for document_chunk_id in result.all() if document_chunk_id is not None]


async def get_corpus_index_indexed_chunks(
    corpus_index_id: int,
    session: AsyncSession,
) -> list[IndexedChunk]:
    result = await session.exec(
        select(IndexedChunk).where(IndexedChunk.corpus_index_id == corpus_index_id)
    )
    return list(result.all())


async def to_corpus_index_read_with_ids(
    index: CorpusIndex,
    session: AsyncSession,
) -> CorpusIndexReadWithIds:
    if index.id is None:
        raise ValueError("Corpus index must be persisted before relationship ids can be loaded")

    return CorpusIndexReadWithIds(
        **index.model_dump(),
        indexed_document_chunk_ids=await get_corpus_index_document_chunk_ids(index.id, session),
    )


async def to_corpus_index_read_with_indexed_chunks(
    index: CorpusIndex,
    session: AsyncSession,
) -> CorpusIndexReadWithIndexedChunks:
    if index.id is None:
        raise ValueError("Corpus index must be persisted before indexed chunks can be loaded")

    indexed_chunks = await get_corpus_index_indexed_chunks(index.id, session)
    return CorpusIndexReadWithIndexedChunks(
        **index.model_dump(),
        indexed_chunks=[
            CorpusIndexIndexedChunkRead(
                document_chunk_id=indexed_chunk.document_chunk_id,
                external_vector_id=indexed_chunk.external_vector_id,
                created_at=indexed_chunk.created_at,
            )
            for indexed_chunk in indexed_chunks
        ],
    )


def ensure_corpus_index_updatable(index: CorpusIndex) -> None:
    if index.status in BLOCKED_GENERAL_UPDATE_STATUSES:
        raise ValueError("Cannot update corpus index while building or built")


async def ensure_corpus_index_deletable(
    index: CorpusIndex,
    session: AsyncSession,
) -> None:
    if index.id is None:
        raise ValueError("Corpus index must be persisted before it can be deleted")

    if await has_indexed_chunks(index.id, session):
        raise ValueError("Cannot delete corpus index with indexed chunks")


async def list_corpus_indices(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    corpus_id: int | None = None,
    vector_store_id: int | None = None,
    chunking_profile_id: int | None = None,
    status: str | None = None,
    has_indexed_chunks: bool | None = None,
) -> list[CorpusIndex]:
    statement = select(CorpusIndex)

    if corpus_id is not None:
        statement = statement.where(CorpusIndex.corpus_id == corpus_id)
    if vector_store_id is not None:
        statement = statement.where(CorpusIndex.vector_store_id == vector_store_id)
    if chunking_profile_id is not None:
        statement = statement.where(CorpusIndex.chunking_profile_id == chunking_profile_id)
    if status is not None:
        ensure_corpus_index_status(status)
        statement = statement.where(CorpusIndex.status == status)
    if has_indexed_chunks is not None:
        indexed_chunk_subquery = select(IndexedChunk.corpus_index_id).distinct()
        if has_indexed_chunks:
            statement = statement.where(CorpusIndex.id.in_(indexed_chunk_subquery))
        else:
            statement = statement.where(CorpusIndex.id.not_in(indexed_chunk_subquery))

    statement = statement.offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def create_corpus_index(
    index_in: CorpusIndexCreate,
    session: AsyncSession,
) -> CorpusIndex:
    await ensure_corpus_index_name_available(index_in.name, session)
    ensure_corpus_index_status(index_in.status)
    ensure_embedding_model(index_in.embedding_model)
    ensure_embedding_dimensions(index_in.embedding_dimensions)
    index = CorpusIndex(**index_in.model_dump())
    return await commit_and_refresh(session, index)


async def update_corpus_index(
    index: CorpusIndex,
    index_in: CorpusIndexUpdate,
    session: AsyncSession,
) -> CorpusIndex:
    ensure_corpus_index_updatable(index)
    update_data = index_in.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] is not None:
        await ensure_corpus_index_name_available(update_data["name"], session, index.id)
    if "status" in update_data and update_data["status"] is not None:
        ensure_status_transition(index.status, update_data["status"])
    if "embedding_model" in update_data:
        ensure_embedding_model(update_data["embedding_model"])
    if "embedding_dimensions" in update_data:
        ensure_embedding_dimensions(update_data["embedding_dimensions"])

    for field_name, value in update_data.items():
        setattr(index, field_name, value)

    index.last_updated = utc_now()
    return await commit_and_refresh(session, index)


async def update_corpus_index_status(
    index: CorpusIndex,
    status_in: CorpusIndexStatusUpdate,
    session: AsyncSession,
) -> CorpusIndex:
    ensure_status_transition(index.status, status_in.status)
    index.status = status_in.status
    index.last_updated = utc_now()
    return await commit_and_refresh(session, index)


async def mark_corpus_index_built(
    index: CorpusIndex,
    build_in: CorpusIndexBuildComplete,
    session: AsyncSession,
) -> CorpusIndex:
    if build_in.status != "built":
        raise ValueError("Build completion status must be built")

    ensure_status_transition(index.status, build_in.status)
    ensure_embedding_dimensions(build_in.embedding_dimensions)
    index.status = build_in.status
    index.built_at = build_in.built_at
    index.embedding_dimensions = build_in.embedding_dimensions
    index.vector_namespace = build_in.vector_namespace
    index.last_updated = utc_now()
    return await commit_and_refresh(session, index)


async def copy_corpus_index(
    source_index: CorpusIndex,
    copy_in: CorpusIndexCopy,
    session: AsyncSession,
) -> CorpusIndex:
    if source_index.id is None:
        raise ValueError("Source corpus index must be persisted before it can be copied")

    await ensure_corpus_index_name_available(copy_in.name, session)
    embedding_model = (
        copy_in.embedding_model
        if copy_in.embedding_model is not None
        else source_index.embedding_model
    )
    embedding_dimensions = (
        copy_in.embedding_dimensions
        if copy_in.embedding_dimensions is not None
        else source_index.embedding_dimensions
    )
    ensure_embedding_model(embedding_model)
    ensure_embedding_dimensions(embedding_dimensions)

    index = CorpusIndex(
        name=copy_in.name,
        corpus_id=copy_in.corpus_id if copy_in.corpus_id is not None else source_index.corpus_id,
        vector_store_id=(
            copy_in.vector_store_id
            if copy_in.vector_store_id is not None
            else source_index.vector_store_id
        ),
        chunking_profile_id=(
            copy_in.chunking_profile_id
            if copy_in.chunking_profile_id is not None
            else source_index.chunking_profile_id
        ),
        status="created",
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        vector_namespace=(
            copy_in.vector_namespace
            if copy_in.vector_namespace is not None
            else source_index.vector_namespace
        ),
        built_at=None,
    )

    try:
        session.add(index)
        await session.flush()

        if index.id is None:
            raise ValueError("Copied corpus index id was not generated")

        source_indexed_chunks = await get_corpus_index_indexed_chunks(source_index.id, session)
        for indexed_chunk in source_indexed_chunks:
            session.add(
                IndexedChunk(
                    corpus_index_id=index.id,
                    document_chunk_id=indexed_chunk.document_chunk_id,
                    external_vector_id=indexed_chunk.external_vector_id,
                )
            )

        await session.commit()
        await session.refresh(index)
        return index
    except Exception:
        await session.rollback()
        raise


async def delete_corpus_index(
    index: CorpusIndex,
    session: AsyncSession,
) -> None:
    await ensure_corpus_index_deletable(index, session)
    await commit_delete(session, index)