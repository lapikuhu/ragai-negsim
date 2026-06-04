from sqlmodel.ext.asyncio.session import AsyncSession

from models.chunking_profiles import ChunkingProfile
from repositories import chunking_profiles_repo
from schemas.chunking_profiles_schemas import (
    ChunkingProfileCopy,
    ChunkingProfileCreate,
    ChunkingProfileReadWithIds,
    ChunkingProfileUpdate,
)


async def _read_chunking_profile_with_ids(
    profile: ChunkingProfile,
    session: AsyncSession,
) -> ChunkingProfileReadWithIds:
    """
    Helper function to convert a ChunkingProfile model instance into a
    ChunkingProfileReadWithIds schema, including fetching associated corpus 
    index IDs.
        Args:
            profile: The ChunkingProfile model instance to convert.
            session: The database session to use for fetching related data.
        Returns:
            A ChunkingProfileReadWithIds object containing the chunking 
            profile data and associated corpus index IDs.
    """
    return await chunking_profiles_repo.to_chunking_profile_read_with_ids(
        profile,
        session,
    )


async def create_chunking_profile_srvc(
    profile_data: ChunkingProfileCreate,
    session: AsyncSession,
) -> ChunkingProfileReadWithIds:
    """
    Create a new chunking profile service function.
        Args:
            profile_data: The data to create the chunking profile with.
            session: The database session.
        Returns:
            A ChunkingProfileReadWithIds object containing the created 
            chunking profile data and associated corpus index IDs.
    """
    profile = await chunking_profiles_repo.create_chunking_profile(
        profile_data,
        session,
    )
    return await _read_chunking_profile_with_ids(profile, session)


async def list_chunking_profiles_srvc(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    strategy: str | None = None,
    name_contains: str | None = None,
    has_references: bool | None = None,
) -> list[ChunkingProfileReadWithIds]:
    """
    List chunking profiles service function with optional filters and 
    pagination.
        Args:
            session: The database session.
            skip: The number of profiles to skip for pagination.
            limit: The maximum number of profiles to return.
            strategy: Optional filter to list profiles by chunking strategy.
            name_contains: Optional filter to list profiles whose names 
                contain a substring.
            has_references: Optional filter to list profiles that are 
                referenced by corpus indices.
        Returns:
            A list of ChunkingProfileReadWithIds objects matching the filters 
            and pagination.
    """
    profiles = await chunking_profiles_repo.list_chunking_profiles(
        session=session,
        skip=skip,
        limit=limit,
        strategy=strategy,
        name_contains=name_contains,
        has_references=has_references,
    )
    return [
        await _read_chunking_profile_with_ids(profile, session)
        for profile in profiles
    ]


async def get_chunking_profile_srvc(
    profile: ChunkingProfile,
    session: AsyncSession,
) -> ChunkingProfileReadWithIds:
    """
    Get a chunking profile by ID service function.
        Args:
            profile: The ChunkingProfile model instance to retrieve.
            session: The database session.
        Returns:
            A ChunkingProfileReadWithIds object containing the chunking 
            profile data and associated corpus index IDs.
    """
    return await _read_chunking_profile_with_ids(profile, session)


async def update_chunking_profile_srvc(
    profile: ChunkingProfile,
    profile_data: ChunkingProfileUpdate,
    session: AsyncSession,
) -> ChunkingProfileReadWithIds:
    """
    Update a chunking profile service function.
        Args:
            profile: The ChunkingProfile model instance to update.
            profile_data: The data to update the chunking profile with.
            session: The database session.
        Returns:
            A ChunkingProfileReadWithIds object containing the updated 
            chunking profile data and associated corpus index IDs.
    """
    updated_profile = await chunking_profiles_repo.update_chunking_profile(
        profile,
        profile_data,
        session,
    )
    return await _read_chunking_profile_with_ids(updated_profile, session)


async def copy_chunking_profile_srvc(
    source_profile: ChunkingProfile,
    copy_data: ChunkingProfileCopy,
    session: AsyncSession,
) -> ChunkingProfileReadWithIds:
    """
    Copy a chunking profile service function.
        Args:
            source_profile: The ChunkingProfile model instance to copy.
            copy_data: The data to create the new copied chunking profile with.
            session: The database session.
        Returns:
            A ChunkingProfileReadWithIds object containing the new copied 
            chunking profile data and associated corpus index IDs.
    """
    copied_profile = await chunking_profiles_repo.copy_chunking_profile(
        source_profile,
        copy_data,
        session,
    )
    return await _read_chunking_profile_with_ids(copied_profile, session)


async def delete_chunking_profile_srvc(
    profile: ChunkingProfile,
    session: AsyncSession,
) -> None:
    """
    Delete a chunking profile service function.
        Args:
            profile: The ChunkingProfile model instance to delete.
            session: The database session.
        Returns:
            None
    """
    await chunking_profiles_repo.delete_chunking_profile(profile, session)
