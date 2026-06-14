from app.models.corpus_indices import CorpusIndex
from app.models.indexed_chunks import IndexedChunk
from app.models.knowledge_graph_indices import KnowledgeGraphIndex
from app.repositories.helpers import commit_and_refresh, commit_delete, utc_now
from app.schemas.corpus_indices_schemas import (
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


ALLOWED_CORPUS_INDEX_STATUSES = {"created", "building", "built", "failed", "cancelled", "retired"}
ALLOWED_STATUS_TRANSITIONS = {
    "created": {"building", "failed", "cancelled"},
    "building": {"built", "failed", "cancelled", "retired"},
    "built": set(),
    "failed": set(),
    "cancelled": set(),
    "retired": set(),
}
BLOCKED_GENERAL_UPDATE_STATUSES = {"building", "built", "retired"}


def ensure_corpus_index_status(status: str) -> None:
    """
    Ensure the provided status is a valid corpus index status.
    Args:
        status: The status to validate.
    Raises:
        ValueError: If the status is not valid.
    """
    if status not in ALLOWED_CORPUS_INDEX_STATUSES:
        raise ValueError("Invalid corpus index status")


def ensure_status_transition(current_status: str, next_status: str) -> None:
    """
    Ensure a corpus index status transition is valid.
    Args:
        current_status: The current status of the corpus index.
        next_status: The desired next status of the corpus index.
    Raises:
        ValueError: If the status transition is not valid.
    """

    ensure_corpus_index_status(current_status)
    ensure_corpus_index_status(next_status)

    if current_status == next_status:
        return

    if next_status not in ALLOWED_STATUS_TRANSITIONS[current_status]:
        raise ValueError("Invalid corpus index status transition")


def ensure_embedding_model(embedding_model: str | None) -> None:
    """
    Ensure the embedding model is not blank if provided.
    Args:
        embedding_model: The embedding model to validate.
    Raises:
        ValueError: If the embedding model is blank.
    """
    if embedding_model is None or not embedding_model.strip():
        raise ValueError("Embedding model must not be blank")


def ensure_embedding_dimensions(embedding_dimensions: int | None) -> None:
    """
    Ensure embedding dimensions is a positive integer if provided.
    Args:
    embedding_dimensions: The number of dimensions for the embedding, or None 
        if not specified.
    Raises:
        ValueError: If embedding_dimensions is not None and is not a 
        positive integer.
    """
    if embedding_dimensions is not None and embedding_dimensions <= 0:
        raise ValueError("Embedding dimensions must be positive")


async def get_corpus_index_by_id(
    index_id: int,
    session: AsyncSession,
) -> CorpusIndex | None:
    """
    Get a corpus index by its ID.
    Args:
        index_id: The ID of the corpus index.
        session: The database session.
    Returns:
        The corpus index instance if found, None otherwise.
    """
    return await session.get(CorpusIndex, index_id)


async def get_corpus_index_by_name(
    name: str,
    session: AsyncSession,
) -> CorpusIndex | None:
    """
    Get a corpus index by its name.
    Args:
        name: The name of the corpus index.
        session: The database session.
    Returns:
        The corpus index instance if found, None otherwise.
    """
    result = await session.exec(select(CorpusIndex).where(CorpusIndex.name == name))
    return result.first()


async def get_replaceable_built_index(
    *,
    corpus_id: int,
    chunking_profile_id: int,
    vector_store_id: int,
    embedding_model: str,
    session: AsyncSession,
) -> CorpusIndex | None:
    result = await session.exec(
        select(CorpusIndex).where(
            CorpusIndex.corpus_id == corpus_id,
            CorpusIndex.chunking_profile_id == chunking_profile_id,
            CorpusIndex.vector_store_id == vector_store_id,
            CorpusIndex.embedding_model == embedding_model,
            CorpusIndex.status == "built",
        )
    )
    return result.first()


async def activate_candidate_index(
    *,
    candidate_index: CorpusIndex,
    requested_name: str,
    session: AsyncSession,
    replaced_index: CorpusIndex | None = None,
) -> tuple[CorpusIndex, CorpusIndex | None]:
    """
    Activate a built candidate index and optionally retire the prior built
    index for the same configuration tuple. This bypasses the general update
    guard for built indices because it is an orchestration-only transition.
    """
    if candidate_index.status != "built":
        raise ValueError("Candidate corpus index must be built before activation")

    if replaced_index is not None:
        if replaced_index.id == candidate_index.id:
            raise ValueError("Candidate corpus index cannot replace itself")
        if replaced_index.status != "built":
            raise ValueError("Only built corpus indexes can be retired during activation")

        replaced_index.status = "retired"
        replaced_index.name = f"{replaced_index.name} [retired {replaced_index.id}]"
        replaced_index.last_updated = utc_now()
        session.add(replaced_index)

    candidate_index.name = requested_name
    candidate_index.last_updated = utc_now()
    session.add(candidate_index)
    await session.commit()
    await session.refresh(candidate_index)
    if replaced_index is not None:
        await session.refresh(replaced_index)
    return candidate_index, replaced_index


async def ensure_corpus_index_name_available(
    name: str,
    session: AsyncSession,
    exclude_index_id: int | None = None,
) -> None:
    """
    Ensure a corpus index name is available.
    Args:
        name: The name of the corpus index.
        session: The database session.
        exclude_index_id: An optional corpus index ID to exclude from 
            the check.
    Raises:
        ValueError: If the corpus index name is already in use.
    """
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
    """
    Check if a corpus index has any indexed chunks.
    Args:
        corpus_index_id: The ID of the corpus index.
        session: The database session.
    Returns:
        True if the corpus index has indexed chunks, False otherwise.
    """
    result = await session.exec(
        select(IndexedChunk.document_chunk_id)
        .where(IndexedChunk.corpus_index_id == corpus_index_id)
        .limit(1)
    )
    return result.first() is not None


async def has_knowledge_graphs(
    corpus_index_id: int,
    session: AsyncSession,
) -> bool:
    """
    Check if a corpus index has any associated knowledge graphs.
    Args:
        corpus_index_id: The ID of the corpus index.
        session: The database session.
    Returns:
        True if the corpus index has associated knowledge graphs, 
        False otherwise.
    """
    result = await session.exec(
        select(KnowledgeGraphIndex.id)
        .where(KnowledgeGraphIndex.corpus_index_id == corpus_index_id)
        .limit(1)
    )
    return result.first() is not None


async def get_corpus_index_document_chunk_ids(
    corpus_index_id: int,
    session: AsyncSession,
) -> list[int]:
    """
    Get the document chunk IDs for a given corpus index.
    Args:
        corpus_index_id: The ID of the corpus index.
        session: The database session.
    Returns:
        A list of document chunk IDs.
    """
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
    """
    Convert a CorpusIndex instance to a list of IndexedChunk instances.
    Args:
        corpus_index_id: The ID of the corpus index.
        session: The database session.
    Returns:
        A list of IndexedChunk instances.
    """
    result = await session.exec(
        select(IndexedChunk).where(IndexedChunk.corpus_index_id == corpus_index_id)
    )
    return list(result.all())


async def to_corpus_index_read_with_ids(
    index: CorpusIndex,
    session: AsyncSession,
) -> CorpusIndexReadWithIds:
    """
    Convert a CorpusIndex instance to a CorpusIndexReadWithIds, 
    including the related document chunk IDs.
    Args:
        index: The corpus index instance to convert.
        session: The database session.
    Returns:
        A CorpusIndexReadWithIds instance.
    """
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
    """
    Convert a CorpusIndex instance to a CorpusIndexReadWithIndexedChunks, 
    including the related indexed chunks.
    Args:
        index: The corpus index instance to convert.
        session: The database session.
    Returns:
        A CorpusIndexReadWithIndexedChunks instance.
    """
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
    """
    Ensure a corpus index can be updated.
    Args:
        index: The corpus index instance to check.
    Raises:
        ValueError: If the corpus index cannot be updated.
    """
    if index.status in BLOCKED_GENERAL_UPDATE_STATUSES:
        raise ValueError("Cannot update corpus index while building or built")


async def ensure_corpus_index_deletable(
    index: CorpusIndex,
    session: AsyncSession,
) -> None:
    """
    Ensure a corpus index can be deleted.
    Args:
        index: The corpus index instance to check.
        session: The database session.
    Raises:
        ValueError: If the corpus index cannot be deleted.
    """
    if index.id is None:
        raise ValueError("Corpus index must be persisted before it can be deleted")

    if await has_knowledge_graphs(index.id, session):
        raise ValueError("Cannot delete corpus index used by a knowledge graph")

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
    """
    List corpus indices with optional filters.
    Args:
        session: The database session.
        skip: The number of records to skip.
        limit: The maximum number of records to return.
        corpus_id: Filter by corpus ID.
        vector_store_id: Filter by vector store ID.
        chunking_profile_id: Filter by chunking profile ID.
        status: Filter by status.
        has_indexed_chunks: Filter by whether the corpus index has indexed chunks.
    Returns:
        A list of corpus indices matching the filters.
    """
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
    """
    Create a new corpus index.
    Args:
        index_in: The data for the new corpus index.
        session: The database session.
    Returns:
        The created corpus index.
    """
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
    """
    Update the status of a corpus index.
    Args:
        index: The corpus index instance to update.
        status_in: The new status for the corpus index.
        session: The database session.
    Returns:
        The updated corpus index.
    """
    ensure_status_transition(index.status, status_in.status)
    index.status = status_in.status
    index.last_updated = utc_now()
    return await commit_and_refresh(session, index)


async def set_corpus_index_build_metadata(
    index: CorpusIndex,
    vector_namespace: str,
    session: AsyncSession,
) -> CorpusIndex:
    """
    Update the build metadata of a corpus index.
    Args:
        index: The corpus index instance to update.
        vector_namespace: The vector namespace for the corpus index.
        session: The database session.
    Returns:
        The updated corpus index.
    """
    index.vector_namespace = vector_namespace
    index.build_error = None
    index.last_updated = utc_now()
    return await commit_and_refresh(session, index)


async def mark_corpus_index_failed(
    index: CorpusIndex,
    build_error: str,
    session: AsyncSession,
) -> CorpusIndex:
    """
    Mark a corpus index as failed.
    Args:
        index: The corpus index instance to update.
        build_error: The error message for the failed build.
        session: The database session.
    Returns:
        The updated corpus index.
    """
    ensure_status_transition(index.status, "failed")
    index.status = "failed"
    index.build_error = build_error
    index.last_updated = utc_now()
    return await commit_and_refresh(session, index)


async def mark_corpus_index_cancelled(
    index: CorpusIndex,
    build_error: str,
    session: AsyncSession,
) -> CorpusIndex:
    """
    Mark a corpus index as cancelled without deleting any partial build data.
    """
    ensure_status_transition(index.status, "cancelled")
    index.status = "cancelled"
    index.build_error = build_error
    index.last_updated = utc_now()
    return await commit_and_refresh(session, index)


async def mark_corpus_index_built(
    index: CorpusIndex,
    build_in: CorpusIndexBuildComplete,
    session: AsyncSession,
) -> CorpusIndex:
    """
    Mark a corpus index as built.
    Args:
        index: The corpus index instance to update.
        build_in: The build completion data for the corpus index.
        session: The database session.
    Returns:
        The updated corpus index.
    """
    if build_in.status != "built":
        raise ValueError("Build completion status must be built")

    ensure_status_transition(index.status, build_in.status)
    ensure_embedding_dimensions(build_in.embedding_dimensions)
    index.status = build_in.status
    index.built_at = build_in.built_at
    index.embedding_dimensions = build_in.embedding_dimensions
    index.vector_namespace = build_in.vector_namespace
    index.build_error = None
    index.last_updated = utc_now()
    return await commit_and_refresh(session, index)


async def copy_corpus_index(
    source_index: CorpusIndex,
    copy_in: CorpusIndexCopy,
    session: AsyncSession,
) -> CorpusIndex:
    """
    Copy a corpus index.
    Args:
        source_index: The source corpus index to copy.
        copy_in: The data for the new corpus index.
        session: The database session.
    Returns:
        The copied corpus index.
    """
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
    """
    Delete a corpus index.
    Args:
        index: The corpus index instance to delete.
        session: The database session.
    Returns:
        None
    """
    await ensure_corpus_index_deletable(index, session)
    await commit_delete(session, index)
