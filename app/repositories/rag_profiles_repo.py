from copy import deepcopy
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.airag.rag_profiles import normalize_rag_profile_config
from app.models.rag_profiles import RagProfile
from app.models.simulations import Simulation
from app.repositories.helpers import commit_and_refresh, commit_delete, utc_now
from app.schemas.rag_profiles_schemas import (
    RagProfileCopy,
    RagProfileCreate,
    RagProfileReadWithIds,
    RagProfileUpdate,
)


def ensure_rag_profile_strategy(strategy: str | None) -> None:
    if strategy is None or not strategy.strip():
        """
        Ensure that the RAG profile strategy is not blank.
        Raises:
            ValueError: If the strategy is blank.
        """
        raise ValueError("RAG strategy must not be blank")


def ensure_rag_profile_config_dict(config: dict[str, Any] | None) -> None:
    """
    Ensure that the RAG profile config is a dictionary.
    Raises:
        ValueError: If the config is not a dictionary.
    """
    if config is not None and not isinstance(config, dict):
        raise ValueError("RAG profile config must be a dictionary")


def normalize_rag_profile_payload(
    strategy: str,
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Normalize and validate a RAG profile payload.
    Args:
        strategy (str): The RAG strategy name.
        config (dict[str, Any] | None): The RAG profile configuration.
    Returns:
        dict[str, Any]: The normalized RAG profile configuration.
    Raises:
        ValueError: If the strategy is blank or the config is not a dictionary.
    """
    ensure_rag_profile_strategy(strategy)
    ensure_rag_profile_config_dict(config)
    return normalize_rag_profile_config(strategy, config)


async def get_rag_profile_by_id(
    profile_id: int,
    session: AsyncSession,
) -> RagProfile | None:
    """
    Get a RAG profile by its ID.
    Args:
        profile_id (int): The ID of the RAG profile.
        session (AsyncSession): The database session.
    Returns:
        RagProfile | None: The RAG profile if found, otherwise None.
    """
    return await session.get(RagProfile, profile_id)


async def get_rag_profile_by_name(
    name: str,
    session: AsyncSession,
) -> RagProfile | None:
    """
    Get a RAG profile by its name.
    Args:
        name (str): The name of the RAG profile.
        session (AsyncSession): The database session.
    Returns:
        RagProfile | None: The RAG profile if found, otherwise None.
    """
    result = await session.exec(select(RagProfile).where(RagProfile.name == name))
    return result.first()


async def ensure_rag_profile_name_available(
    name: str,
    session: AsyncSession,
    exclude_profile_id: int | None = None,
) -> None:
    """
    Ensure that a RAG profile name is available (not already used).
    Args:
        name (str): The name of the RAG profile to check.
        session (AsyncSession): The database session.
        exclude_profile_id (int | None): An optional profile ID to exclude 
        from the check.
    Returns:
        None
    Raises:
        ValueError: If the RAG profile name is already in use.
    """
    existing = await get_rag_profile_by_name(name, session)
    if existing is None:
        return
    if exclude_profile_id is not None and existing.id == exclude_profile_id:
        return
    raise ValueError("RAG profile name already exists")


async def rag_profile_has_simulations(
    profile_id: int,
    session: AsyncSession,
) -> bool:
    """
    Check if a RAG profile has been used in any simulations.
    Args:
        profile_id (int): The ID of the RAG profile.
        session (AsyncSession): The database session.
    Returns:
        bool: True if the RAG profile has been used in simulations,
        False otherwise.
    """
    result = await session.exec(
        select(Simulation.id).where(Simulation.rag_profile_id == profile_id).limit(1)
    )
    return result.first() is not None


async def ensure_rag_profile_unused(
    profile: RagProfile,
    session: AsyncSession,
) -> None:
    """
    Ensure that the RAG profile is not used in any simulations.
    Args:
        profile (RagProfile): The RAG profile to check.
        session (AsyncSession): The database session.
    Raises:
        ValueError: If the RAG profile has been used in simulations.
    """
    if profile.id is None:
        raise ValueError("RAG profile must be persisted before this operation")
    if await rag_profile_has_simulations(profile.id, session):
        raise ValueError("Cannot modify RAG profile that has been used in simulations")


async def list_rag_profiles(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    strategy: str | None = None,
    name_contains: str | None = None,
    used: bool | None = None,
    created_by_user_id: int | None = None,
) -> list[RagProfile]:
    """
    List RAG profiles with optional filtering and pagination.
    Args:
        session (AsyncSession): The database session.
        skip (int): The number of records to skip for pagination.
        limit (int): The maximum number of records to return.
        strategy (str | None): Optional filter for RAG strategy.
        name_contains (str | None): Optional filter for names containing 
            a substring.
        used (bool | None): Optional filter for whether the profile has 
            been used in simulations.
        created_by_user_id (int | None): Optional filter for profiles 
            created by a specific user.
    Returns:
        list[RagProfile]: A list of RAG profiles matching the filters.
    """
    statement = select(RagProfile)

    if strategy is not None:
        statement = statement.where(RagProfile.strategy == strategy)
    if name_contains is not None:
        statement = statement.where(RagProfile.name.contains(name_contains))
    if created_by_user_id is not None:
        statement = statement.where(RagProfile.created_by_user_id == created_by_user_id)
    if used is not None:
        used_subquery = (
            select(Simulation.rag_profile_id)
            .where(Simulation.rag_profile_id.is_not(None))
            .distinct()
        )
        if used:
            statement = statement.where(RagProfile.id.in_(used_subquery))
        else:
            statement = statement.where(RagProfile.id.not_in(used_subquery))

    statement = statement.offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def get_rag_profile_simulation_ids(
    profile_id: int,
    session: AsyncSession,
) -> list[int]:
    """
    Get the IDs of simulations associated with a RAG profile.
    Args:
        profile_id (int): The ID of the RAG profile.
        session (AsyncSession): The database session.
    Returns:
        list[int]: A list of simulation IDs associated with the RAG profile.
    """
    result = await session.exec(
        select(Simulation.id).where(Simulation.rag_profile_id == profile_id)
    )
    return [simulation_id for simulation_id in result.all() if simulation_id is not None]


async def to_rag_profile_read_with_ids(
    profile: RagProfile,
    session: AsyncSession,
) -> RagProfileReadWithIds:
    """
    Convert a RAG profile to a RAG profile read model with associated 
    simulation IDs.
    Args:
        profile (RagProfile): The RAG profile to convert.
        session (AsyncSession): The database session.
    Returns:
        RagProfileReadWithIds: The RAG profile read model with simulation IDs.
    """
    if profile.id is None:
        raise ValueError("RAG profile must be persisted before relationship ids can be loaded")
    return RagProfileReadWithIds(
        **profile.model_dump(),
        simulation_ids=await get_rag_profile_simulation_ids(profile.id, session),
    )


async def create_rag_profile(
    profile_in: RagProfileCreate,
    session: AsyncSession,
) -> RagProfile:
    """
    Create a new RAG profile.
    Args:
        profile_in (RagProfileCreate): The RAG profile creation data.
        session (AsyncSession): The database session.
    Returns:
        RagProfile: The created RAG profile.
    """
    await ensure_rag_profile_name_available(profile_in.name, session)
    normalized_config = normalize_rag_profile_payload(
        profile_in.strategy,
        profile_in.config,
    )
    profile = RagProfile(
        name=profile_in.name,
        strategy=profile_in.strategy,
        config=normalized_config,
        created_by_user_id=profile_in.created_by_user_id,
    )
    return await commit_and_refresh(session, profile)


async def update_rag_profile(
    profile: RagProfile,
    profile_in: RagProfileUpdate,
    session: AsyncSession,
) -> RagProfile:
    """
    Update an existing RAG profile.
    Args:
        profile (RagProfile): The existing RAG profile to update.
        profile_in (RagProfileUpdate): The RAG profile update data.
        session (AsyncSession): The database session.
    Returns:
        RagProfile: The updated RAG profile.
    """
    await ensure_rag_profile_unused(profile, session)
    update_data = profile_in.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] is not None:
        await ensure_rag_profile_name_available(update_data["name"], session, profile.id)

    next_strategy = update_data.get("strategy", profile.strategy)
    next_config = update_data.get("config", profile.config)
    if "strategy" in update_data or "config" in update_data:
        update_data["strategy"] = next_strategy
        update_data["config"] = normalize_rag_profile_payload(next_strategy, next_config)

    for field_name, value in update_data.items():
        setattr(profile, field_name, value)

    profile.last_updated = utc_now()
    return await commit_and_refresh(session, profile)


async def copy_rag_profile(
    source_profile: RagProfile,
    copy_in: RagProfileCopy,
    created_by_user_id: int,
    session: AsyncSession,
) -> RagProfile:
    """
    Copy an existing RAG profile to create a new one.
    Args:
        source_profile (RagProfile): The existing RAG profile to copy.
        copy_in (RagProfileCopy): The RAG profile copy data.
        created_by_user_id (int): The ID of the user creating the copy.
        session (AsyncSession): The database session.
    Returns:
        RagProfile: The newly created RAG profile copy.
    """
    await ensure_rag_profile_name_available(copy_in.name, session)
    strategy = copy_in.strategy if copy_in.strategy is not None else source_profile.strategy
    config = copy_in.config if copy_in.config is not None else deepcopy(source_profile.config)
    normalized_config = normalize_rag_profile_payload(strategy, config)
    profile = RagProfile(
        name=copy_in.name,
        strategy=strategy,
        config=normalized_config,
        created_by_user_id=created_by_user_id,
    )
    return await commit_and_refresh(session, profile)


async def delete_rag_profile(
    profile: RagProfile,
    session: AsyncSession,
) -> None:
    """
    Delete a RAG profile if it has not been used in any simulations.
    Args:
        profile (RagProfile): The RAG profile to delete.
        session (AsyncSession): The database session.
    Returns:
        None
    """
    await ensure_rag_profile_unused(profile, session)
    await commit_delete(session, profile)
