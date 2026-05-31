from models.scenarios import Scenario
from models.simulations import Simulation
from repositories.helpers import commit_and_refresh, commit_delete, utc_now
from schemas.scenarios_schemas import (
    ScenarioCopy,
    ScenarioCreate,
    ScenarioReadWithIds,
    ScenarioUpdate,
)
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


async def scenario_has_simulations(
    scenario_id: int,
    session: AsyncSession,
) -> bool:
    result = await session.exec(
        select(Simulation.id).where(Simulation.scenario_id == scenario_id).limit(1)
    )
    return result.first() is not None


async def ensure_scenario_unused(
    scenario: Scenario,
    session: AsyncSession,
) -> None:
    if scenario.id is None:
        raise ValueError("Scenario must be persisted before this operation")

    if await scenario_has_simulations(scenario.id, session):
        raise ValueError("Cannot modify scenario that has been used in a simulation")


async def get_scenario_by_id(
    scenario_id: int,
    session: AsyncSession,
) -> Scenario | None:
    return await session.get(Scenario, scenario_id)


async def get_scenario_by_name(
    name: str,
    session: AsyncSession,
) -> Scenario | None:
    result = await session.exec(select(Scenario).where(Scenario.name == name))
    return result.first()


async def ensure_scenario_name_available(
    name: str,
    session: AsyncSession,
    exclude_scenario_id: int | None = None,
) -> None:
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
    result = await session.exec(select(Simulation.id).where(Simulation.scenario_id == scenario_id))
    return [simulation_id for simulation_id in result.all() if simulation_id is not None]


async def to_scenario_read_with_ids(
    scenario: Scenario,
    session: AsyncSession,
) -> ScenarioReadWithIds:
    if scenario.id is None:
        raise ValueError("Scenario must be persisted before relationship ids can be loaded")

    return ScenarioReadWithIds(
        **scenario.model_dump(),
        simulation_ids=await get_scenario_simulation_ids(scenario.id, session),
    )


async def create_scenario(
    scenario_in: ScenarioCreate,
    session: AsyncSession,
) -> Scenario:
    await ensure_scenario_name_available(scenario_in.name, session)
    scenario = Scenario(**scenario_in.model_dump())
    return await commit_and_refresh(session, scenario)


async def update_scenario(
    scenario: Scenario,
    scenario_in: ScenarioUpdate,
    session: AsyncSession,
) -> Scenario:
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
    await ensure_scenario_name_available(copy_in.name, session)
    scenario = Scenario(
        name=copy_in.name,
        description=(
            copy_in.description
            if copy_in.description is not None
            else source_scenario.description
        ),
        created_by_user_id=copy_in.created_by_user_id,
    )
    return await commit_and_refresh(session, scenario)


async def delete_scenario(
    scenario: Scenario,
    session: AsyncSession,
) -> None:
    await ensure_scenario_unused(scenario, session)
    await commit_delete(session, scenario)