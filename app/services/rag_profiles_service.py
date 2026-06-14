from sqlmodel.ext.asyncio.session import AsyncSession

from app.airag.rag_profiles import list_rag_profile_definitions
from app.models.rag_profiles import RagProfile
from app.models.users import User
from app.repositories import rag_profiles_repo
from app.schemas.rag_profile_definitions_schemas import (
    RagProfileDefinitionRead,
    RagProfileFieldDefinitionRead,
)
from app.schemas.rag_profiles_schemas import (
    RagProfileCopy,
    RagProfileCreate,
    RagProfileCreateRequest,
    RagProfileReadWithIds,
    RagProfileUpdate,
    RagProfileUpdateRequest,
)


async def create_rag_profile_srvc(
    profile_data: RagProfileCreateRequest,
    session: AsyncSession,
    current_user: User,
) -> RagProfileReadWithIds:
    """
    Create a new RAG profile service.
    Args:
        profile_data (RagProfileCreateRequest): The RAG profile creation 
            request data.
        session (AsyncSession): The database session.
        current_user (User): The current user creating the profile.
    Returns:
        RagProfileReadWithIds: The created RAG profile read model with 
        associated simulation IDs.
    """
    profile_in = RagProfileCreate(
        **profile_data.model_dump(),
        created_by_user_id=current_user.id,
    )
    profile = await rag_profiles_repo.create_rag_profile(profile_in, session)
    return await rag_profiles_repo.to_rag_profile_read_with_ids(profile, session)


async def list_rag_profile_definitions_srvc() -> list[RagProfileDefinitionRead]:
    """
    List all available RAG profile definitions service.
    Args:
        None
    Returns:
        list[RagProfileDefinitionRead]: A list of RAG profile definitions read
        models.
    """
    return [
        RagProfileDefinitionRead(
            strategy=definition.strategy,
            label=definition.label,
            fields=[
                RagProfileFieldDefinitionRead(
                    name=field.name,
                    kind=field.kind,
                    label=field.label,
                    required=field.required,
                    default=field.default,
                    minimum=field.minimum,
                    maximum=field.maximum,
                    help_text=field.help_text,
                    options=list(field.options),
                )
                for field in definition.fields
            ],
        )
        for definition in list_rag_profile_definitions()
    ]


async def list_rag_profiles_srvc(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    strategy: str | None = None,
    name_contains: str | None = None,
    used: bool | None = None,
    created_by_user_id: int | None = None,
) -> list[RagProfileReadWithIds]:
    """
    List RAG profiles service with optional filtering and pagination.
    Args:
        session (AsyncSession): The database session.
        skip (int): The number of profiles to skip for pagination.
        limit (int): The maximum number of profiles to return.
        strategy (str | None): Optional filter for RAG strategy.
        name_contains (str | None): Optional filter for profiles whose names
            contain the given substring.
        used (bool | None): Optional filter for profiles that have been used
            in simulations (True) or not (False).
        created_by_user_id (int | None): Optional filter for profiles created
            by a specific user ID.
    Returns:
        list[RagProfileReadWithIds]: A list of RAG profile read models with
        associated simulation IDs.
    """
    profiles = await rag_profiles_repo.list_rag_profiles(
        session=session,
        skip=skip,
        limit=limit,
        strategy=strategy,
        name_contains=name_contains,
        used=used,
        created_by_user_id=created_by_user_id,
    )
    return [
        await rag_profiles_repo.to_rag_profile_read_with_ids(profile, session)
        for profile in profiles
    ]


async def get_rag_profile_srvc(
    profile: RagProfile,
    session: AsyncSession,
) -> RagProfileReadWithIds:
    """
    Get a RAG profile service.
    Args:
        profile (RagProfile): The RAG profile to retrieve.
        session (AsyncSession): The database session.
    Returns:
        RagProfileReadWithIds: The RAG profile read model with associated
        simulation IDs.
    """
    return await rag_profiles_repo.to_rag_profile_read_with_ids(profile, session)


async def update_rag_profile_srvc(
    profile: RagProfile,
    profile_data: RagProfileUpdateRequest,
    session: AsyncSession,
    current_user: User,
) -> RagProfileReadWithIds:
    """
    Update a RAG profile service.
    Args:
        profile (RagProfile): The RAG profile to update.
        profile_data (RagProfileUpdateRequest): The data to update the RAG 
            profile with.
        session (AsyncSession): The database session.
        current_user (User): The current user performing the update.
    Returns:
        RagProfileReadWithIds: The updated RAG profile read model with 
        associated simulation IDs.
    """
    profile_in = RagProfileUpdate(
        **profile_data.model_dump(exclude_unset=True),
        last_edit_by_user_id=current_user.id,
    )
    updated = await rag_profiles_repo.update_rag_profile(profile, profile_in, session)
    return await rag_profiles_repo.to_rag_profile_read_with_ids(updated, session)


async def copy_rag_profile_srvc(
    source_profile: RagProfile,
    copy_data: RagProfileCopy,
    session: AsyncSession,
    current_user: User,
) -> RagProfileReadWithIds:
    """
    Copy a RAG profile service.
    Args:
        source_profile (RagProfile): The RAG profile to copy.
        copy_data (RagProfileCopy): The data for the new copied RAG profile.
        session (AsyncSession): The database session.
        current_user (User): The current user performing the copy.
    Returns:
        RagProfileReadWithIds: The copied RAG profile read model with 
        associated simulation IDs.
    """
    copied = await rag_profiles_repo.copy_rag_profile(
        source_profile,
        copy_data,
        current_user.id,
        session,
    )
    return await rag_profiles_repo.to_rag_profile_read_with_ids(copied, session)


async def delete_rag_profile_srvc(
    profile: RagProfile,
    session: AsyncSession,
) -> None:
    """
    Delete a RAG profile service if it has not been used in any simulations.
    Args:
        profile (RagProfile): The RAG profile to delete.
        session (AsyncSession): The database session.
    Returns:
        None
    """
    await rag_profiles_repo.delete_rag_profile(profile, session)
