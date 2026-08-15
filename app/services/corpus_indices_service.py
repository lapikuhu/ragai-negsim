from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.corpus_indices import CorpusIndex
from app.repositories import (
    chunking_profiles_repo,
    corpus_indices_repo,
    corpus_chunk_sets_repo,
    corpus_repo,
    vector_stores_repo,
)
from app.services import simulations_service
from app.schemas.corpus_indices_schemas import (
    CorpusIndexBuildComplete,
    CorpusIndexCopy,
    CorpusIndexCreate,
    CorpusIndexMetadataUpdate,
    CorpusIndexReadWithIds,
    CorpusIndexReadWithIndexedChunks,
    CorpusIndexStatusUpdate,
    CorpusIndexUpdate,
)


async def _read_corpus_index_with_ids(
    index: CorpusIndex,
    session: AsyncSession,
) -> CorpusIndexReadWithIds:
    """
    Helper to read a corpus index and the indexed chunked documents ids
    Args:
        index (CorpusIndex): the corpus index to read
        session (AsyncSession): the database session
    Returns:
        CorpusIndexReadWithIds: the corpus index with the indexed chunked documents ids
    """
    value = await corpus_indices_repo.to_corpus_index_read_with_ids(index, session)
    chunk_set = await corpus_chunk_sets_repo.get_corpus_chunk_set_by_id(
        index.corpus_chunk_set_id, session
    )
    reason = None
    if chunk_set is None:
        reason = "Corpus chunk set no longer exists"
    elif index.corpus_chunk_set_revision != chunk_set.revision:
        reason = "Corpus chunk set revision changed"
    elif index.corpus_chunk_set_checksum != chunk_set.document_chunk_ids_checksum:
        reason = "Corpus chunk set checksum changed"
    return value.model_copy(
        update={"is_stale": reason is not None, "stale_reason": reason}
    )


async def _ensure_corpus_exists(corpus_id: int, session: AsyncSession) -> None:
    if await corpus_repo.get_corpus_by_id(corpus_id, session) is None:
        """
        Helper to ensure a corpus exists by its ID
        Args:
            corpus_id (int): the ID of the corpus to check
            session (AsyncSession): the database session
        Returns:
            None
         Raises:     
            ValueError: if the corpus does not exist
         """
        raise ValueError("Corpus not found")


async def _ensure_vector_store_exists(vector_store_id: int, session: AsyncSession) -> None:
    if await vector_stores_repo.get_vector_store_by_id(vector_store_id, session) is None:
        """
        Helper to ensure a vector store exists by its ID
        Args:
            vector_store_id (int): the ID of the vector store to check
            session (AsyncSession): the database session
        Returns:
            None
         Raises:     
            ValueError: if the vector store does not exist
         """
        raise ValueError("Vector store not found")


async def _ensure_chunking_profile_exists(profile_id: int, session: AsyncSession) -> None:
    if await chunking_profiles_repo.get_chunking_profile_by_id(profile_id, session) is None:
        """
        Helper to ensure a chunking profile exists by its ID
        Args:
            profile_id (int): the ID of the chunking profile to check
            session (AsyncSession): the database session
        Returns:
            None
        Raises:     
            ValueError: if the chunking profile does not exist
        """
        raise ValueError("Chunking profile not found")


async def _ensure_required_refs_exist(
    corpus_id: int,
    vector_store_id: int,
    chunking_profile_id: int,
    session: AsyncSession,
) -> None:
    """
    Helper to ensure all required references exist by their IDs
    Args:
        corpus_id (int): the ID of the corpus to check
        vector_store_id (int): the ID of the vector store to check
        chunking_profile_id (int): the ID of the chunking profile to check
        session (AsyncSession): the database session
    Returns:
        None
    Raises:
        ValueError: if any of the required references do not exist
    """
    await _ensure_corpus_exists(corpus_id, session)
    await _ensure_vector_store_exists(vector_store_id, session)
    await _ensure_chunking_profile_exists(chunking_profile_id, session)


async def _ensure_chunk_set_identity(
    *,
    corpus_id: int,
    chunking_profile_id: int,
    corpus_chunk_set_id: int,
    corpus_chunk_set_revision: int,
    corpus_chunk_set_checksum: str,
    session: AsyncSession,
) -> None:
    """
    Perform checks to ensure that the corpus chunk set identity matches the 
    expected values.
    
    Args:
        corpus_id (int): The ID of the corpus to check.
        chunking_profile_id (int): The ID of the chunking profile to check.
        corpus_chunk_set_id (int): The ID of the corpus chunk set to check.
        corpus_chunk_set_revision (int): The expected revision of the corpus 
            chunk set.
        corpus_chunk_set_checksum (str): The expected checksum of the corpus 
            chunk set.
        session (AsyncSession): The database session.
    Raises:
        ValueError: If any of the checks fail.
    
    """
    chunk_set = await corpus_chunk_sets_repo.get_corpus_chunk_set_by_id(
        corpus_chunk_set_id, session
    )
    if chunk_set is None:
        raise ValueError("Corpus chunk set not found")
    if chunk_set.corpus_id != corpus_id:
        raise ValueError("Corpus chunk set does not belong to corpus")
    if chunk_set.chunking_profile_id != chunking_profile_id:
        raise ValueError("Corpus chunk set uses a different chunking profile")
    if chunk_set.revision != corpus_chunk_set_revision:
        raise ValueError("Corpus chunk set revision changed")
    if chunk_set.document_chunk_ids_checksum != corpus_chunk_set_checksum:
        raise ValueError("Corpus chunk set checksum changed")

# CHECK
async def _ensure_copy_override_refs_exist(
    copy_data: CorpusIndexCopy,
    session: AsyncSession,
) -> None:
    """
    Helper to ensure all required references exist by their IDs, considering 
    possible overrides
    Args:
        copy_data (CorpusIndexCopy): the copy data containing possible 
            overrides
        session (AsyncSession): the database session
    Returns:
        None
    Raises:
        ValueError: if any of the required references do not exist
    """
    if copy_data.corpus_id is not None:
        await _ensure_corpus_exists(copy_data.corpus_id, session)
    if copy_data.vector_store_id is not None:
        await _ensure_vector_store_exists(copy_data.vector_store_id, session)
    if copy_data.chunking_profile_id is not None:
        await _ensure_chunking_profile_exists(copy_data.chunking_profile_id, session)


async def create_corpus_index_srvc(
    index_data: CorpusIndexCreate,
    session: AsyncSession,
) -> CorpusIndexReadWithIds:
    """
    Service to create a new corpus index
    Args:
        index_data (CorpusIndexCreate): the data for the new corpus index
        session (AsyncSession): the database session
    Returns:
        CorpusIndexReadWithIds: the created corpus index with IDs
    Raises:
        ValueError: if any of the required references do not exist
    """
    await _ensure_required_refs_exist(
        index_data.corpus_id,
        index_data.vector_store_id,
        index_data.chunking_profile_id,
        session,
    )
    # Check the chunk set identity to ensure it matches the expected values
    await _ensure_chunk_set_identity(
        corpus_id=index_data.corpus_id,
        chunking_profile_id=index_data.chunking_profile_id,
        corpus_chunk_set_id=index_data.corpus_chunk_set_id,
        corpus_chunk_set_revision=index_data.corpus_chunk_set_revision,
        corpus_chunk_set_checksum=index_data.corpus_chunk_set_checksum,
        session=session,
    )
    index = await corpus_indices_repo.create_corpus_index(index_data, session)
    return await _read_corpus_index_with_ids(index, session)


async def list_corpus_indices_srvc(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    corpus_id: int | None = None,
    vector_store_id: int | None = None,
    chunking_profile_id: int | None = None,
    status: str | None = None,
    has_indexed_chunks: bool | None = None,
) -> list[CorpusIndexReadWithIds]:
    """
    Service to list corpus indices
    Args:
        session (AsyncSession): the database session
        skip (int): the number of items to skip
        limit (int): the maximum number of items to return
        corpus_id (int | None): filter by corpus ID
        vector_store_id (int | None): filter by vector store ID
        chunking_profile_id (int | None): filter by chunking profile ID
        status (str | None): filter by status
        has_indexed_chunks (bool | None): filter by whether the index has 
            indexed chunks
    Returns:
        list[CorpusIndexReadWithIds]: the list of corpus indices with IDs
    """
    indices = await corpus_indices_repo.list_corpus_indices(
        session=session,
        skip=skip,
        limit=limit,
        corpus_id=corpus_id,
        vector_store_id=vector_store_id,
        chunking_profile_id=chunking_profile_id,
        status=status,
        has_indexed_chunks=has_indexed_chunks,
    )
    return [await _read_corpus_index_with_ids(index, session) for index in indices]


async def get_corpus_index_srvc(
    index: CorpusIndex,
    session: AsyncSession,
) -> CorpusIndexReadWithIds:
    """
    Service to get a corpus index by its ID
    Args:
        index (CorpusIndex): the corpus index to get
        session (AsyncSession): the database session
    Returns:
        CorpusIndexReadWithIds: the corpus index with IDs
    """
    return await _read_corpus_index_with_ids(index, session)


async def get_corpus_index_detail_srvc(
    index: CorpusIndex,
    session: AsyncSession,
) -> CorpusIndexReadWithIndexedChunks:
    """
    Service to get a corpus index with its indexed chunks
    Args:
        index (CorpusIndex): the corpus index to get
        session (AsyncSession): the database session
    Returns:
        CorpusIndexReadWithIndexedChunks: the corpus index with indexed chunks
    """
    value = await corpus_indices_repo.to_corpus_index_read_with_indexed_chunks(
        index,
        session,
    )
    chunk_set = await corpus_chunk_sets_repo.get_corpus_chunk_set_by_id(
        index.corpus_chunk_set_id, session
    )
    # Get the chunk set and perform staleness checks on it
    reason = None
    if chunk_set is None:
        reason = "Corpus chunk set no longer exists"
    elif index.corpus_chunk_set_revision != chunk_set.revision:
        reason = "Corpus chunk set revision changed"
    elif index.corpus_chunk_set_checksum != chunk_set.document_chunk_ids_checksum:
        reason = "Corpus chunk set checksum changed"
    return value.model_copy(
        update={"is_stale": reason is not None, "stale_reason": reason}
    )

# CHECK
async def update_corpus_index_srvc(
    index: CorpusIndex,
    index_data: CorpusIndexMetadataUpdate,
    session: AsyncSession,
) -> CorpusIndexReadWithIds:
    """
    Service to update a corpus index's metadata
    Args:
        index (CorpusIndex): the corpus index to update
        index_data (CorpusIndexMetadataUpdate): the metadata update data
        session (AsyncSession): the database session
    Returns:
        CorpusIndexReadWithIds: the updated corpus index with IDs
    """
    update_data = index_data.model_dump(exclude_unset=True)
    update_in = CorpusIndexUpdate(**update_data)
    updated_index = await corpus_indices_repo.update_corpus_index(
        index,
        update_in,
        session,
    )
    return await _read_corpus_index_with_ids(updated_index, session)


async def update_corpus_index_status_srvc(
    index: CorpusIndex,
    status_data: CorpusIndexStatusUpdate,
    session: AsyncSession,
) -> CorpusIndexReadWithIds:
    """
    Service to update a corpus index's status
    Args:
        index (CorpusIndex): the corpus index to update
        status_data (CorpusIndexStatusUpdate): the status update data
        session (AsyncSession): the database session
    Returns:
        CorpusIndexReadWithIds: the updated corpus index with IDs
    """
    updated_index = await corpus_indices_repo.update_corpus_index_status(
        index,
        status_data,
        session,
    )
    return await _read_corpus_index_with_ids(updated_index, session)


async def mark_corpus_index_built_srvc(
    index: CorpusIndex,
    build_data: CorpusIndexBuildComplete,
    session: AsyncSession,
) -> CorpusIndexReadWithIds:
    """
    Service to mark a corpus index as built
    Args:
        index (CorpusIndex): the corpus index to mark as built
        build_data (CorpusIndexBuildComplete): the build completion data
        session (AsyncSession): the database session
    Returns:
        CorpusIndexReadWithIds: the updated corpus index with IDs
    """
    updated_index = await corpus_indices_repo.mark_corpus_index_built(
        index,
        build_data,
        session,
    )
    return await _read_corpus_index_with_ids(updated_index, session)


async def copy_corpus_index_srvc(
    source_index: CorpusIndex,
    copy_data: CorpusIndexCopy,
    session: AsyncSession,
) -> CorpusIndexReadWithIds:
    """
    Service to copy a corpus index
    Args:
        source_index (CorpusIndex): the source corpus index to copy
        copy_data (CorpusIndexCopy): the copy data
        session (AsyncSession): the database session
    Returns:
        CorpusIndexReadWithIds: the copied corpus index with IDs
    """
    await _ensure_copy_override_refs_exist(copy_data, session)
    if copy_data.corpus_id not in (None, source_index.corpus_id):
        raise ValueError("Cannot copy a corpus index to a different corpus chunk set")
    if copy_data.chunking_profile_id not in (
        None,
        source_index.chunking_profile_id,
    ):
        raise ValueError("Cannot copy a corpus index to a different chunking profile")
    await _ensure_chunk_set_identity(
        corpus_id=source_index.corpus_id,
        chunking_profile_id=source_index.chunking_profile_id,
        corpus_chunk_set_id=source_index.corpus_chunk_set_id,
        corpus_chunk_set_revision=source_index.corpus_chunk_set_revision,
        corpus_chunk_set_checksum=source_index.corpus_chunk_set_checksum,
        session=session,
    )
    copied_index = await corpus_indices_repo.copy_corpus_index(
        source_index,
        copy_data,
        session,
    )
    return await _read_corpus_index_with_ids(copied_index, session)


async def delete_corpus_index_srvc(
    index: CorpusIndex,
    session: AsyncSession,
) -> None:
    """
    Service to delete a corpus index
    Args:
        index (CorpusIndex): the corpus index to delete
        session (AsyncSession): the database session
    Returns:
        None
    """
    try:
        await corpus_indices_repo.delete_corpus_index(index, session)
    finally:
        simulations_service.clear_negotiation_graph_cache_for_corpus_index(index.id)
