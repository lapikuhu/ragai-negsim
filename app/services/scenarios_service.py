from textwrap import dedent

from sqlmodel.ext.asyncio.session import AsyncSession
from langchain_core.runnables.config import RunnableConfig

from app.airag.observability.llm_usage import invoke_with_config
from app.models.scenarios import Scenario
from app.models.users import User
from app.repositories import scenarios_repo
from app.schemas.scenarios_schemas import (
    ScenarioAuthoringReadWithIds,
    ScenarioContextGenerateRequest,
    ScenarioContextGenerateResponse,
    ScenarioContextGenerationModel,
    ScenarioCopy,
    ScenarioCopyRequest,
    ScenarioCreate,
    ScenarioCreateRequest,
    ScenarioPublicReadWithIds,
    ScenarioUpdate,
    ScenarioUpdateRequest,
)


def _build_scenario_context_generation_prompt(
    scenario_data: ScenarioContextGenerateRequest,
) -> str:
    return dedent(
        f"""
        You are generating structured context for a negotiation simulator.

        Split the scenario into exactly three sections:
        1. public_context: facts both sides can know
        2. side_a_private_context: facts only Side A should know
        3. side_b_private_context: facts only Side B should know

        Keep the structure useful and readable. Do not return markdown.

        Scenario name:
        {scenario_data.name}

        Scenario description:
        {scenario_data.description}
        """
    ).strip()


async def generate_scenario_context_srvc(
    scenario_data: ScenarioContextGenerateRequest,
    model,
    config: RunnableConfig | None = None,
) -> ScenarioContextGenerateResponse:
    """
    Generate structured context for a negotiation scenario using the 
    provided model. Split to public, side_a and side_b.
    Args:
        scenario_data (ScenarioContextGenerateRequest): The data for the 
            scenario context generation.
        model: The language model to use for generating the context.
    Returns:
        ScenarioContextGenerateResponse: The generated scenario context.
    """
    try:
        structured_model = model.with_structured_output(
            ScenarioContextGenerationModel,
            method="function_calling",
        )
        result = invoke_with_config(
            structured_model,
            _build_scenario_context_generation_prompt(scenario_data),
            config,
        )
        if hasattr(result, "model_dump"):
            payload = result.model_dump()
        elif hasattr(result, "__dict__"):
            payload = result.__dict__
        else:
            payload = result
        validated = ScenarioContextGenerationModel.model_validate(payload)
        return ScenarioContextGenerateResponse(**validated.model_dump())
    except Exception as exc:
        raise ValueError("Unable to generate scenario context right now") from exc


async def create_scenario_srvc(
    scenario_data: ScenarioCreateRequest,
    session: AsyncSession,
    current_user: User,
) -> ScenarioAuthoringReadWithIds:
    """
    Create a new scenario.
    Args:
        scenario_data (ScenarioCreateRequest): The data for the scenario to be created.
        session (AsyncSession): The database session.
        current_user (User): The current user creating the scenario.

    Returns:
        ScenarioAuthoringReadWithIds: The created scenario with its IDs.
    """
    scenario_in = ScenarioCreate(
        **scenario_data.model_dump(),
        created_by_user_id=current_user.id,
    )
    scenario = await scenarios_repo.create_scenario(scenario_in, session)
    return await scenarios_repo.to_scenario_authoring_read_with_ids(scenario, session)


async def list_scenarios_srvc(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    created_by_user_id: int | None = None,
    name_contains: str | None = None,
    used: bool | None = None,
) -> list[ScenarioPublicReadWithIds]:
    """
    List scenarios with optional filters.
    Args:
        session (AsyncSession): The database session.
        skip (int): Number of scenarios to skip for pagination.
        limit (int): Maximum number of scenarios to return.
        created_by_user_id (int | None): Filter by creator user ID.
        name_contains (str | None): Filter by name containing this string.
        used (bool | None): Filter by usage status.

    Returns:
        list[ScenarioPublicReadWithIds]: A list of scenarios matching the filters.
    """
    scenarios = await scenarios_repo.list_scenarios(
        session=session,
        skip=skip,
        limit=limit,
        created_by_user_id=created_by_user_id,
        name_contains=name_contains,
        used=used,
    )
    return [
        await scenarios_repo.to_scenario_public_read_with_ids(scenario, session)
        for scenario in scenarios
    ]


async def get_scenario_srvc(
    scenario: Scenario,
    session: AsyncSession,
) -> ScenarioPublicReadWithIds:
    """
    Get a scenario by its ID.
    Args:
        scenario (Scenario): The scenario to retrieve.
        session (AsyncSession): The database session.

    Returns:
        ScenarioPublicReadWithIds: The retrieved scenario with its IDs.
    """
    return await scenarios_repo.to_scenario_public_read_with_ids(scenario, session)


async def get_scenario_authoring_srvc(
    scenario: Scenario,
    session: AsyncSession,
) -> ScenarioAuthoringReadWithIds:
    """
    Get a scenario authoring details by its ID.
    Args:
        scenario (Scenario): The scenario to retrieve.
        session (AsyncSession): The database session.
    Returns:
        ScenarioAuthoringReadWithIds: The retrieved scenario with its IDs 
        for authoring.
    """
    return await scenarios_repo.to_scenario_authoring_read_with_ids(scenario, session)


async def update_scenario_srvc(
    scenario: Scenario,
    scenario_data: ScenarioUpdateRequest,
    session: AsyncSession,
    current_user: User,
) -> ScenarioAuthoringReadWithIds:
    """
    Update an existing scenario.
    Args:
        scenario (Scenario): The scenario to update.
        scenario_data (ScenarioUpdateRequest): The data for updating the 
            scenario.
        session (AsyncSession): The database session.
        current_user (User): The current user updating the scenario.
    Returns:
        ScenarioAuthoringReadWithIds: The updated scenario with its IDs.
    """
    scenario_in = ScenarioUpdate(
        **scenario_data.model_dump(exclude_unset=True),
        last_edit_by_user_id=current_user.id,
    )
    updated_scenario = await scenarios_repo.update_scenario(
        scenario,
        scenario_in,
        session,
    )
    return await scenarios_repo.to_scenario_authoring_read_with_ids(updated_scenario, session)


async def copy_scenario_srvc(
    source_scenario: Scenario,
    copy_data: ScenarioCopyRequest,
    session: AsyncSession,
    current_user: User,
) -> ScenarioAuthoringReadWithIds:
    """
    Copy an existing scenario.
    Args:
        source_scenario (Scenario): The scenario to copy.
        copy_data (ScenarioCopyRequest): The data for copying the scenario.
        session (AsyncSession): The database session.
        current_user (User): The current user performing the copy.
    Returns:
        ScenarioAuthoringReadWithIds: The copied scenario with its IDs.
    """
    copy_in = ScenarioCopy(
        **copy_data.model_dump(),
        created_by_user_id=current_user.id,
    )
    copied_scenario = await scenarios_repo.copy_scenario(
        source_scenario,
        copy_in,
        session,
    )
    return await scenarios_repo.to_scenario_authoring_read_with_ids(copied_scenario, session)


async def delete_scenario_srvc(
    scenario: Scenario,
    session: AsyncSession,
) -> None:
    """
    Delete an existing scenario.
    Args:
        scenario (Scenario): The scenario to delete.
        session (AsyncSession): The database session.
    Returns:
        None
    """
    await scenarios_repo.delete_scenario(scenario, session)
