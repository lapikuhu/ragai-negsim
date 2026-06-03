from fastapi import APIRouter, HTTPException, status

from core.dependencies import (
    CurrentUserDep,
    ScenarioCreatorDep,
    ScenarioViewerDep,
    SessionDep,
    WritableScenarioDep,
)
from schemas.scenarios_schemas import (
    ScenarioCopyRequest,
    ScenarioCreateRequest,
    ScenarioReadWithIds,
    ScenarioUpdateRequest,
)
from services import scenarios_service


router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def _raise_scenario_service_error(exc: ValueError) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    ) from exc


@router.post(
    "/",
    response_model=ScenarioReadWithIds,
    status_code=status.HTTP_201_CREATED,
)
async def create_scenario(
    scenario_data: ScenarioCreateRequest,
    session: SessionDep,
    current_user: ScenarioCreatorDep,
) -> ScenarioReadWithIds:
    try:
        return await scenarios_service.create_scenario_srvc(
            scenario_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_scenario_service_error(exc)


@router.get(
    "/",
    response_model=list[ScenarioReadWithIds],
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
) -> list[ScenarioReadWithIds]:
    return await scenarios_service.list_scenarios_srvc(
        session=session,
        skip=skip,
        limit=limit,
        created_by_user_id=created_by_user_id,
        name_contains=name_contains,
        used=used,
    )


@router.get(
    "/{scenario_id}",
    response_model=ScenarioReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def get_scenario(
    scenario: ScenarioViewerDep,
    session: SessionDep,
) -> ScenarioReadWithIds:
    try:
        return await scenarios_service.get_scenario_srvc(scenario, session)
    except ValueError as exc:
        _raise_scenario_service_error(exc)


@router.patch(
    "/{scenario_id}",
    response_model=ScenarioReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def update_scenario(
    scenario_data: ScenarioUpdateRequest,
    scenario: WritableScenarioDep,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ScenarioReadWithIds:
    try:
        return await scenarios_service.update_scenario_srvc(
            scenario,
            scenario_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_scenario_service_error(exc)


@router.post(
    "/{scenario_id}/copy",
    response_model=ScenarioReadWithIds,
    status_code=status.HTTP_201_CREATED,
)
async def copy_scenario(
    copy_data: ScenarioCopyRequest,
    source_scenario: ScenarioViewerDep,
    session: SessionDep,
    current_user: ScenarioCreatorDep,
) -> ScenarioReadWithIds:
    try:
        return await scenarios_service.copy_scenario_srvc(
            source_scenario,
            copy_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_scenario_service_error(exc)


@router.delete(
    "/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_scenario(
    scenario: WritableScenarioDep,
    session: SessionDep,
) -> None:
    try:
        await scenarios_service.delete_scenario_srvc(scenario, session)
    except ValueError as exc:
        _raise_scenario_service_error(exc)
