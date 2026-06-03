from sqlmodel.ext.asyncio.session import AsyncSession

from models.scenarios import Scenario
from models.users import User
from repositories import scenarios_repo
from schemas.scenarios_schemas import (
    ScenarioCopy,
    ScenarioCopyRequest,
    ScenarioCreate,
    ScenarioCreateRequest,
    ScenarioReadWithIds,
    ScenarioUpdate,
    ScenarioUpdateRequest,
)


async def create_scenario_srvc(
    scenario_data: ScenarioCreateRequest,
    session: AsyncSession,
    current_user: User,
) -> ScenarioReadWithIds:
    scenario_in = ScenarioCreate(
        **scenario_data.model_dump(),
        created_by_user_id=current_user.id,
    )
    scenario = await scenarios_repo.create_scenario(scenario_in, session)
    return await scenarios_repo.to_scenario_read_with_ids(scenario, session)


async def list_scenarios_srvc(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    created_by_user_id: int | None = None,
    name_contains: str | None = None,
    used: bool | None = None,
) -> list[ScenarioReadWithIds]:
    scenarios = await scenarios_repo.list_scenarios(
        session=session,
        skip=skip,
        limit=limit,
        created_by_user_id=created_by_user_id,
        name_contains=name_contains,
        used=used,
    )
    return [
        await scenarios_repo.to_scenario_read_with_ids(scenario, session)
        for scenario in scenarios
    ]


async def get_scenario_srvc(
    scenario: Scenario,
    session: AsyncSession,
) -> ScenarioReadWithIds:
    return await scenarios_repo.to_scenario_read_with_ids(scenario, session)


async def update_scenario_srvc(
    scenario: Scenario,
    scenario_data: ScenarioUpdateRequest,
    session: AsyncSession,
    current_user: User,
) -> ScenarioReadWithIds:
    scenario_in = ScenarioUpdate(
        **scenario_data.model_dump(exclude_unset=True),
        last_edit_by_user_id=current_user.id,
    )
    updated_scenario = await scenarios_repo.update_scenario(
        scenario,
        scenario_in,
        session,
    )
    return await scenarios_repo.to_scenario_read_with_ids(updated_scenario, session)


async def copy_scenario_srvc(
    source_scenario: Scenario,
    copy_data: ScenarioCopyRequest,
    session: AsyncSession,
    current_user: User,
) -> ScenarioReadWithIds:
    copy_in = ScenarioCopy(
        **copy_data.model_dump(),
        created_by_user_id=current_user.id,
    )
    copied_scenario = await scenarios_repo.copy_scenario(
        source_scenario,
        copy_in,
        session,
    )
    return await scenarios_repo.to_scenario_read_with_ids(copied_scenario, session)


async def delete_scenario_srvc(
    scenario: Scenario,
    session: AsyncSession,
) -> None:
    await scenarios_repo.delete_scenario(scenario, session)
