from copy import deepcopy
from typing import Any
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# local imports
from app.models.chunking_profiles import ChunkingProfile
from app.models.corpus_indices import CorpusIndex
from app.models.document_chunks import DocumentChunk
from app.repositories.helpers import commit_and_refresh, commit_delete, utc_now
from app.schemas.chunking_profiles_schemas import (
    ChunkingProfileCopy,
    ChunkingProfileCreate,
    ChunkingProfileReadWithIds,
    ChunkingProfileUpdate,
)


def ensure_chunking_profile_config_dict(config: dict[str, Any] | None) -> None:
    """
    Ensure that the chunking profile config is a dictionary if provided.
    Args:
        config: The chunking profile config.
    Raises:
        ValueError: If the chunking profile config is not a dictionary.
    """
    if not isinstance(config, dict):
        raise ValueError("Chunking profile config must be a dictionary")


def ensure_chunking_strategy(strategy: str | None) -> None:
    """
    Ensure that a chunking strategy is provided.
    Args:
        strategy: The chunking strategy.
    Raises:
        ValueError: If the chunking strategy is blank.
    """
    if strategy is None or not strategy.strip():
        raise ValueError("Chunking strategy must not be blank")


async def get_chunking_profile_by_id(
    profile_id: int,
    session: AsyncSession,
) -> ChunkingProfile | None:
    """
    Fetch a chunking profile by its ID.
    Args:
        profile_id: The ID of the chunking profile.
        session: The database session.
    Returns:
        The chunking profile if found, otherwise None.
    """
    return await session.get(ChunkingProfile, profile_id)


async def get_chunking_profile_by_name(
    name: str,
    session: AsyncSession,
) -> ChunkingProfile | None:
    """
    Fetch a chunking profile by its name.
    Args:
        name: The name of the chunking profile.
        session: The database session.
    Returns:
        The chunking profile if found, otherwise None.
    """
    result = await session.exec(select(ChunkingProfile).where(ChunkingProfile.name == name))
    return result.first()


async def ensure_chunking_profile_name_available(
    name: str,
    session: AsyncSession,
    exclude_profile_id: int | None = None,
) -> None:
    """
    Ensure that a chunking profile name is available.
    Args:
        name: The name of the chunking profile.
        session: The database session.
        exclude_profile_id: An optional profile ID to exclude from the check.
    Raises:
        ValueError: If the chunking profile name already exists.
    """
    existing_profile = await get_chunking_profile_by_name(name, session)
    if existing_profile is None:
        return

    if exclude_profile_id is not None and existing_profile.id == exclude_profile_id:
        return

    raise ValueError("Chunking profile name already exists")


async def has_document_chunks(
    profile_id: int,
    session: AsyncSession,
) -> bool:
    """
    Check if a chunking profile has associated document chunks.
    Args:
        profile_id: The ID of the chunking profile.
        session: The database session.
    Returns:
        True if the chunking profile has document chunks, otherwise False.
    """
    result = await session.exec(
        select(DocumentChunk.id)
        .where(DocumentChunk.chunking_profile_id == profile_id)
        .limit(1)
    )
    return result.first() is not None


async def has_corpus_indices(     
    profile_id: int,
    session: AsyncSession,
) -> bool:
    """
    Check if a chunking profile has associated corpus indices.
    Args:
        profile_id: The ID of the chunking profile.
        session: The database session.
    Returns:
        True if the chunking profile has corpus indices, otherwise False.
    """
    result = await session.exec(
        select(CorpusIndex.id)
        .where(CorpusIndex.chunking_profile_id == profile_id)
        .limit(1)
    )
    return result.first() is not None


async def chunking_profile_has_references(
    profile_id: int,
    session: AsyncSession,
) -> bool:
    """
    Check if a chunking profile has any references (document chunks or corpus indices).
    Args:
        profile_id: The ID of the chunking profile.
        session: The database session.
    Returns:
        True if the chunking profile has any references, otherwise False.
    """
    return (
        await has_document_chunks(profile_id, session)
        or await has_corpus_indices(profile_id, session)
    )


async def ensure_chunking_profile_can_update(
    profile: ChunkingProfile,
    update_data: dict[str, Any],
    session: AsyncSession,
) -> None:
    """
    Ensure that a chunking profile can be updated.
    Args:
        profile: The chunking profile to check.
        update_data: The update data.
        session: The database session.
    Raises:
        ValueError: If the chunking profile cannot be updated.
    """
    if profile.id is None:
        raise ValueError("Chunking profile must be persisted before it can be updated")

    if not {"strategy", "config"}.intersection(update_data):
        return

    if await chunking_profile_has_references(profile.id, session):
        raise ValueError("Cannot update strategy or config for referenced chunking profile")


async def ensure_chunking_profile_deletable(
    profile: ChunkingProfile,
    session: AsyncSession,
) -> None:
    """
    Ensure that a chunking profile can be deleted.
    Args:
        profile: The chunking profile to check.
        session: The database session.
    Raises:
        ValueError: If the chunking profile cannot be deleted.
    """
    if profile.id is None:
        raise ValueError("Chunking profile must be persisted before it can be deleted")

    if await has_document_chunks(profile.id, session):
        raise ValueError("Cannot delete chunking profile with existing document chunks")

    if await has_corpus_indices(profile.id, session):
        raise ValueError("Cannot delete chunking profile with existing corpus indexes")


async def list_chunking_profiles(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    strategy: str | None = None,
    name_contains: str | None = None,
    has_references: bool | None = None,
) -> list[ChunkingProfile]:
    """
    List chunking profiles with optional filters.
    Args:
        session: The database session.
        skip: The number of profiles to skip.
        limit: The maximum number of profiles to return.
        strategy: Optional strategy filter.
        name_contains: Optional name filter.
        has_references: Optional filter for profiles with references.
    Returns:
        A list of chunking profiles.
    """
    statement = select(ChunkingProfile)

    if strategy is not None:
        statement = statement.where(ChunkingProfile.strategy == strategy)
    if name_contains is not None:
        statement = statement.where(ChunkingProfile.name.contains(name_contains))
    if has_references is not None:
        document_chunk_subquery = select(DocumentChunk.chunking_profile_id).distinct()
        corpus_index_subquery = select(CorpusIndex.chunking_profile_id).distinct()
        has_document_chunks_filter = ChunkingProfile.id.in_(document_chunk_subquery)
        has_corpus_indices_filter = ChunkingProfile.id.in_(corpus_index_subquery)
        if has_references:
            statement = statement.where(has_document_chunks_filter | has_corpus_indices_filter)
        else:
            statement = statement.where(
                ChunkingProfile.id.not_in(document_chunk_subquery),
                ChunkingProfile.id.not_in(corpus_index_subquery),
            )

    statement = statement.offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def get_chunking_profile_document_chunk_ids(
    profile_id: int,
    session: AsyncSession,
) -> list[int]:
    """
    Get the IDs of document chunks associated with a chunking profile.
    Args:
        profile_id: The ID of the chunking profile.
        session: The database session.
    Returns:
        A list of document chunk IDs.
    """
    result = await session.exec(
        select(DocumentChunk.id).where(DocumentChunk.chunking_profile_id == profile_id)
    )
    return [document_chunk_id for document_chunk_id in result.all() if document_chunk_id is not None]


async def get_chunking_profile_corpus_index_ids(
    profile_id: int,
    session: AsyncSession,
) -> list[int]:
    """
    Get the IDs of corpus indices associated with a chunking profile.
    Args:
        profile_id: The ID of the chunking profile.
        session: The database session.
    Returns:
        A list of corpus index IDs.
    """
    result = await session.exec(
        select(CorpusIndex.id).where(CorpusIndex.chunking_profile_id == profile_id)
    )
    return [corpus_index_id for corpus_index_id in result.all() if corpus_index_id is not None]


async def to_chunking_profile_read_with_ids(
    profile: ChunkingProfile,
    session: AsyncSession,
) -> ChunkingProfileReadWithIds:
    """
    Convert a ChunkingProfile to a ChunkingProfileReadWithIds, including related IDs.
    Args:
        profile: The chunking profile.
        session: The database session.
    Returns:
        A ChunkingProfileReadWithIds instance.
    """
    if profile.id is None:
        raise ValueError("Chunking profile must be persisted before relationship ids can be loaded")

    return ChunkingProfileReadWithIds(
        **profile.model_dump(),
        document_chunk_ids=await get_chunking_profile_document_chunk_ids(profile.id, session),
        corpus_index_ids=await get_chunking_profile_corpus_index_ids(profile.id, session),
    )


async def create_chunking_profile(
    profile_in: ChunkingProfileCreate,
    session: AsyncSession,
) -> ChunkingProfile:
    """
    Create a new chunking profile.
    Args:
        profile_in: The chunking profile data.
        session: The database session.
    Returns:
        The created chunking profile.
    """
    await ensure_chunking_profile_name_available(profile_in.name, session)
    ensure_chunking_strategy(profile_in.strategy)
    ensure_chunking_profile_config_dict(profile_in.config)
    profile = ChunkingProfile(**profile_in.model_dump())
    return await commit_and_refresh(session, profile)


async def update_chunking_profile(
    profile: ChunkingProfile,
    profile_in: ChunkingProfileUpdate,
    session: AsyncSession,
) -> ChunkingProfile:
    """
    Update an existing chunking profile.
    Args:
        profile: The chunking profile to update.
        profile_in: The update data.
        session: The database session.
    Returns:
        The updated chunking profile.
    """
    update_data = profile_in.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] is not None:
        await ensure_chunking_profile_name_available(update_data["name"], session, profile.id)
    if "strategy" in update_data:
        ensure_chunking_strategy(update_data["strategy"])
    if "config" in update_data:
        ensure_chunking_profile_config_dict(update_data["config"])

    await ensure_chunking_profile_can_update(profile, update_data, session)

    for field_name, value in update_data.items():
        setattr(profile, field_name, value)

    profile.last_updated = utc_now()
    return await commit_and_refresh(session, profile)


async def copy_chunking_profile(
    source_profile: ChunkingProfile,
    copy_in: ChunkingProfileCopy,
    session: AsyncSession,
) -> ChunkingProfile:
    """
    Copy an existing chunking profile.
    Args:
        source_profile: The chunking profile to copy.
        copy_in: The copy data.
        session: The database session.
    Returns:
        The copied chunking profile.
    """
    await ensure_chunking_profile_name_available(copy_in.name, session)
    strategy = copy_in.strategy if copy_in.strategy is not None else source_profile.strategy
    config = copy_in.config if copy_in.config is not None else deepcopy(source_profile.config)

    ensure_chunking_strategy(strategy)
    ensure_chunking_profile_config_dict(config)

    profile = ChunkingProfile(
        name=copy_in.name,
        strategy=strategy,
        config=config,
    )
    return await commit_and_refresh(session, profile)


async def delete_chunking_profile(
    profile: ChunkingProfile,
    session: AsyncSession,
) -> None:
    """
    Delete a chunking profile.
    Args:
        profile: The chunking profile to delete.
        session: The database session.
    """
    await ensure_chunking_profile_deletable(profile, session)
    await commit_delete(session, profile)