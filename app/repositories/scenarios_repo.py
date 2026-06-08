from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# local imports
from app.models.scenarios import Scenario
from app.models.simulations import Simulation
from app.repositories.helpers import commit_and_refresh, commit_delete, utc_now
from app.schemas.scenarios_schemas import (
    ScenarioAuthoringReadWithIds,
    ScenarioCopy,
    ScenarioCreate,
    ScenarioPublicReadWithIds,
    ScenarioUpdate,
)

async def scenario_has_simulations(
    scenario_id: int,
    session: AsyncSession,
) -> bool:
    """
    Check if a scenario has been used in any simulations.
        Args:
            scenario_id: The ID of the scenario to check.
            session: The database session.
        Returns:
            True if the scenario has been used in at least one simulation, 
            False otherwise.
    """
    result = await session.exec(
        select(Simulation.id).where(Simulation.scenario_id == scenario_id).limit(1)
    )
    return result.first() is not None


async def ensure_scenario_unused(
    scenario: Scenario,
    session: AsyncSession,
) -> None:
    """
    Ensure that a scenario has not been used in any simulations.
        Args:
            scenario: The scenario to check.
            session: The database session.
        Returns:
            None
        Raises:
            ValueError: If the scenario has been used in any simulations.
    """
    if scenario.id is None:
        raise ValueError("Scenario must be persisted before this operation")

    if await scenario_has_simulations(scenario.id, session):
        raise ValueError("Cannot modify scenario that has been used in a simulation")


async def get_scenario_by_id(
    scenario_id: int,
    session: AsyncSession,
) -> Scenario | None:
    """
    Get a scenario by its ID.
        Args:
            scenario_id: The ID of the scenario to retrieve.
            session: The database session.
        Returns:
            The Scenario instance if found, else None.
    """
    return await session.get(Scenario, scenario_id)


async def get_scenario_by_name(
    name: str,
    session: AsyncSession,
) -> Scenario | None:
    """
    Get a scenario by its name.
        Args:
            name: The name of the scenario to retrieve.
            session: The database session.
        Returns:
            The Scenario instance if found, else None.
    """
    result = await session.exec(select(Scenario).where(Scenario.name == name))
    return result.first()


async def ensure_scenario_name_available(
    name: str,
    session: AsyncSession,
    exclude_scenario_id: int | None = None,
) -> None:
    """
    Ensure that a scenario name is available.
        Args:
            name: The name of the scenario to check.
            session: The database session.
            exclude_scenario_id: Optional scenario ID to exclude from the check.
        Returns:
            None
        Raises:
            ValueError: If the scenario name already exists.
    """
    existing_scenario = await get_scenario_by_name(name, session)
    if existing_scenario is None:
        return

    if exclude_scenario_id is not None and existing_scenario.id == exclude_scenario_id:
        return

    raise ValueError("Scenario name already exists")


async def list_scenarios(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    created_by_user_id: int | None = None,
    name_contains: str | None = None,
    used: bool | None = None,
) -> list[Scenario]:
    """
    List scenarios with optional filters.
        Args:
            session: The database session.
            skip: Number of records to skip.
            limit: Maximum number of records to return.
            created_by_user_id: Optional user ID filter.
            name_contains: Optional name filter.
            used: Optional filter for scenarios used in simulations.
        Returns:
            A list of Scenario instances.
    """
    statement = select(Scenario)

    if created_by_user_id is not None:
        statement = statement.where(Scenario.created_by_user_id == created_by_user_id)
    if name_contains is not None:
        statement = statement.where(Scenario.name.contains(name_contains))
    if used is not None:
        used_subquery = select(Simulation.scenario_id).where(Simulation.scenario_id.is_not(None)).distinct()
        if used:
            statement = statement.where(Scenario.id.in_(used_subquery))
        else:
            statement = statement.where(Scenario.id.not_in(used_subquery))

    statement = statement.offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def get_scenario_simulation_ids(
    scenario_id: int,
    session: AsyncSession,
) -> list[int]:
    """
    Get the IDs of simulations associated with a scenario.
        Args:
            scenario_id: The ID of the scenario.
            session: The database session.
        Returns:
            A list of simulation IDs.
    """
    result = await session.exec(select(Simulation.id).where(Simulation.scenario_id == scenario_id))
    return [simulation_id for simulation_id in result.all() if simulation_id is not None]


async def to_scenario_authoring_read_with_ids(
    scenario: Scenario,
    session: AsyncSession,
) -> ScenarioAuthoringReadWithIds:
    """
    Convert a Scenario instance to a ScenarioAuthoringReadWithIds instance, including 
    related simulation IDs.
        Args:
            scenario: The Scenario instance to convert.
            session: The database session.
        Returns:
            A ScenarioAuthoringReadWithIds instance.
        Raises:
            ValueError: If the scenario has not been persisted.
    """
    if scenario.id is None:
        raise ValueError("Scenario must be persisted before relationship ids can be loaded")

    return ScenarioAuthoringReadWithIds(
        **scenario.model_dump(),
        simulation_ids=await get_scenario_simulation_ids(scenario.id, session),
    )


async def to_scenario_public_read_with_ids(
    scenario: Scenario,
    session: AsyncSession,
) -> ScenarioPublicReadWithIds:
    """
    Convert a Scenario instance to a ScenarioPublicReadWithIds instance, 
    including related simulation IDs.
        Args:
            scenario: The Scenario instance to convert.
            session: The database session.
        Returns:
            A ScenarioPublicReadWithIds instance.
        Raises:
            ValueError: If the scenario has not been persisted.
    """
    if scenario.id is None:
        raise ValueError("Scenario must be persisted before relationship ids can be loaded")

    return ScenarioPublicReadWithIds(
        id=scenario.id,
        name=scenario.name,
        public_context=scenario.public_context,
        created_by_user_id=scenario.created_by_user_id,
        last_edit_by_user_id=scenario.last_edit_by_user_id,
        created_at=scenario.created_at,
        last_updated=scenario.last_updated,
        simulation_ids=await get_scenario_simulation_ids(scenario.id, session),
    )


async def create_scenario(
    scenario_in: ScenarioCreate,
    session: AsyncSession,
) -> Scenario:
    """
    Create a new scenario.
        Args:
            scenario_in: The ScenarioCreate instance containing scenario data.
            session: The database session.
        Returns:
            The created Scenario instance.
        Raises:
            ValueError: If the scenario name is already in use.
    """
    await ensure_scenario_name_available(scenario_in.name, session)
    scenario = Scenario(**scenario_in.model_dump())
    return await commit_and_refresh(session, scenario)


async def update_scenario(
    scenario: Scenario,
    scenario_in: ScenarioUpdate,
    session: AsyncSession,
) -> Scenario:
    """
    Update an existing scenario.
        Args:
            scenario: The Scenario instance to update.
            scenario_in: The ScenarioUpdate instance containing updated data.
            session: The database session.
        Returns:
            The updated Scenario instance.
        Raises:
            ValueError: If the scenario is already in use or the new name is 
            not available.
    """
    await ensure_scenario_unused(scenario, session)
    update_data = scenario_in.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] is not None:
        await ensure_scenario_name_available(update_data["name"], session, scenario.id)

    for field_name, value in update_data.items():
        setattr(scenario, field_name, value)

    scenario.last_updated = utc_now()
    return await commit_and_refresh(session, scenario)


async def copy_scenario(
    source_scenario: Scenario,
    copy_in: ScenarioCopy,
    session: AsyncSession,
) -> Scenario:
    """
    Copy an existing scenario.
        Args:
            source_scenario: The Scenario instance to copy.
            copy_in: The ScenarioCopy instance containing copy data.
            session: The database session.
        Returns:
            The copied Scenario instance.
        Raises:
            ValueError: If the scenario name is already in use.
    """
    await ensure_scenario_name_available(copy_in.name, session)
    scenario = Scenario(
        name=copy_in.name,
        description=(
            copy_in.description
            if copy_in.description is not None
            else source_scenario.description
        ),
        public_context=source_scenario.public_context,
        side_a_private_context=source_scenario.side_a_private_context,
        side_b_private_context=source_scenario.side_b_private_context,
        created_by_user_id=copy_in.created_by_user_id,
    )
    return await commit_and_refresh(session, scenario)


async def delete_scenario(
    scenario: Scenario,
    session: AsyncSession,
) -> None:
    """
    Delete an existing scenario.
        Args:
            scenario: The Scenario instance to delete.
            session: The database session.
        Raises:
            ValueError: If the scenario is in use.
    """
    await ensure_scenario_unused(scenario, session)
    await commit_delete(session, scenario)
