from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import (
    ChatModelDep,
    CurrentUserDep,
    ScenarioCreatorDep,
    ScenarioViewerDep,
    SessionDep,
    WritableScenarioDep,
)
from app.schemas.scenarios_schemas import (
    ScenarioAuthoringReadWithIds,
    ScenarioContextGenerateRequest,
    ScenarioContextGenerateResponse,
    ScenarioCopyRequest,
    ScenarioCreateRequest,
    ScenarioPublicReadWithIds,
    ScenarioUpdateRequest,
)
from app.services import scenarios_service

# Declare the API router for scenario-related endpoints
router = APIRouter(prefix="/scenarios", tags=["scenarios"])

def _raise_scenario_service_error(exc: ValueError) -> None:
    """
    Helper function to raise HTTP exceptions based on ValueError from 
    scenario services.
    Args:
        exc (ValueError): The exception raised by the scenario service.
    Raises:
        HTTPException: An HTTP exception with status code 409 and the error message.
    """
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    ) from exc

### ------------------------ CREATE SCENARIO ----------------------- ###
@router.post(
    "/",
    response_model=ScenarioAuthoringReadWithIds,
    status_code=status.HTTP_201_CREATED,
)
async def create_scenario(
    scenario_data: ScenarioCreateRequest,
    session: SessionDep,
    current_user: ScenarioCreatorDep,
) -> ScenarioAuthoringReadWithIds:
    """
    Create a new scenario endpoint.
    Args:
        scenario_data (ScenarioCreateRequest): The data for the scenario 
            to be created.
        session (SessionDep): The database session dependency.
        current_user (ScenarioCreatorDep): The current user dependency with 
            scenario creation permissions.
    Returns:
        ScenarioAuthoringReadWithIds: The created scenario with its IDs.
    """
    try:
        return await scenarios_service.create_scenario_srvc(
            scenario_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_scenario_service_error(exc)

### ------------------------ LIST SCENARIOS ----------------------- ###
@router.get(
    "/",
    response_model=list[ScenarioPublicReadWithIds],
    status_code=status.HTTP_200_OK,
)
async def list_scenarios(
    session: SessionDep,
    _current_user: CurrentUserDep,
    skip: int = 0,
    limit: int = 20,
    created_by_user_id: int | None = None,
    name_contains: str | None = None,
    used: bool | None = None,
) -> list[ScenarioPublicReadWithIds]:
    """
    List scenarios with optional filters.
    Args:
        session (SessionDep): The database session dependency.
        _current_user (CurrentUserDep): The current user dependency (not used in this endpoint but can be used for future enhancements).
        skip (int): Number of scenarios to skip for pagination.
        limit (int): Maximum number of scenarios to return.
        created_by_user_id (int | None): Filter scenarios by creator user ID.
        name_contains (str | None): Filter scenarios by name containing this string.
        used (bool | None): Filter scenarios by usage status.
    Returns:
        list[ScenarioPublicReadWithIds]: A list of scenarios matching the filters.
    """
    return await scenarios_service.list_scenarios_srvc(
        session=session,
        skip=skip,
        limit=limit,
        created_by_user_id=created_by_user_id,
        name_contains=name_contains,
        used=used,
    )


@router.post(
    "/generate-context",
    response_model=ScenarioContextGenerateResponse,
    status_code=status.HTTP_200_OK,
)
async def generate_scenario_context(
    scenario_data: ScenarioContextGenerateRequest,
    model: ChatModelDep,
    _current_user: ScenarioCreatorDep,
) -> ScenarioContextGenerateResponse:
    try:
        return await scenarios_service.generate_scenario_context_srvc(
            scenario_data,
            model,
        )
    except ValueError as exc:
        _raise_scenario_service_error(exc)

### ----------------------- GET SCENARIO BY ID --------------------- ###
@router.get(
    "/{scenario_id}",
    response_model=ScenarioPublicReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def get_scenario(
    scenario: ScenarioViewerDep,
    session: SessionDep,
) -> ScenarioPublicReadWithIds:
    """
    Get a scenario by its ID.
    Args:
        scenario (ScenarioViewerDep): The scenario dependency.
        session (SessionDep): The database session dependency.
    Returns:
        ScenarioPublicReadWithIds: The scenario with its IDs.
    Raises:
        HTTPException: If the scenario is not found or if there is an error retrieving the scenario.
    """
    try:
        return await scenarios_service.get_scenario_srvc(scenario, session)
    except ValueError as exc:
        _raise_scenario_service_error(exc)


@router.get(
    "/{scenario_id}/authoring",
    response_model=ScenarioAuthoringReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def get_scenario_authoring(
    scenario: WritableScenarioDep,
    session: SessionDep,
) -> ScenarioAuthoringReadWithIds:
    try:
        return await scenarios_service.get_scenario_authoring_srvc(scenario, session)
    except ValueError as exc:
        _raise_scenario_service_error(exc)

### ------------------------- UPDATE SCENARIO ---------------------- ###
@router.patch(
    "/{scenario_id}",
    response_model=ScenarioAuthoringReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def update_scenario(
    scenario_data: ScenarioUpdateRequest,
    scenario: WritableScenarioDep,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ScenarioAuthoringReadWithIds:
    """
    Update an existing scenario.
    Args:
        scenario_data (ScenarioUpdateRequest): The data for updating the 
            scenario.
        scenario (WritableScenarioDep): The scenario dependency with write 
            permissions.
        session (SessionDep): The database session dependency.
        current_user (CurrentUserDep): The current user dependency.
    Returns:
        ScenarioAuthoringReadWithIds: The updated scenario with its IDs.
    """
    try:
        return await scenarios_service.update_scenario_srvc(
            scenario,
            scenario_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_scenario_service_error(exc)

### -------------------------- COPY SCENARIO ----------------------- ###
@router.post(
    "/{scenario_id}/copy",
    response_model=ScenarioAuthoringReadWithIds,
    status_code=status.HTTP_201_CREATED,
)
async def copy_scenario(
    copy_data: ScenarioCopyRequest,
    source_scenario: ScenarioViewerDep,
    session: SessionDep,
    current_user: ScenarioCreatorDep,
) -> ScenarioAuthoringReadWithIds:
    """
    Copy an existing scenario.
    Args:
        copy_data (ScenarioCopyRequest): The data for copying the scenario.
        source_scenario (ScenarioViewerDep): The source scenario dependency.
        session (SessionDep): The database session dependency.
        current_user (ScenarioCreatorDep): The current user dependency with 
            scenario creation permissions.
    Returns:
        ScenarioAuthoringReadWithIds: The copied scenario with its IDs.
    Raises:
        HTTPException: If there is an error copying the scenario.
    """
    try:
        return await scenarios_service.copy_scenario_srvc(
            source_scenario,
            copy_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_scenario_service_error(exc)

### ------------------------- DELETE SCENARIO ---------------------- ###
@router.delete(
    "/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_scenario(
    scenario: WritableScenarioDep,
    session: SessionDep,
) -> None:
    """
    Delete an existing scenario.
    Args:
        scenario (WritableScenarioDep): The scenario dependency with write 
            permissions.
        session (SessionDep): The database session dependency.
    Raises:
        HTTPException: If there is an error deleting the scenario.
    """
    try:
        await scenarios_service.delete_scenario_srvc(scenario, session)
    except ValueError as exc:
        _raise_scenario_service_error(exc)
