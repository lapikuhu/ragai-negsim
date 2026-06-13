from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import (
    AccessibleSimulationDep,
    CurrentUserDep,
    Page,
    ReadableSimulationDep,
    SessionDep,
    TeacherOrAdminDep,
    TeacherReviewSimulationDep,
)
from app.schemas.simulations_schemas import (
    SimulationCreateRequest,
    SimulationEvaluationListResponse,
    SimulationProxyDisableResponse,
    SimulationProxyTurnRequest,
    SimulationProxyTurnResponse,
    SimulationRead,
    SimulationReadWithState,
    SimulationStartRequest,
    SimulationStatus,
    SimulationTeacherReviewRequest,
    SimulationTurnRequest,
    SimulationTurnResponse,
    SimulationUpdateRequest,
)
from app.services import simulations_service

# TODO: Consider moving the review endpoints to a separate route file for 
# better organization.

# Declare the API router for simulations
router = APIRouter(prefix="/simulations", tags=["simulations"])

# CHECK
def _raise_simulation_service_error(exc: ValueError) -> None:
    """
    Raise an HTTPException with a 409 Conflict status code for 
    simulation service errors.
    """
    detail = str(exc)
    if detail in {
        "Corpus not found",
        "Corpus index not found",
        "Vector store not found",
        "Scenario not found",
        "Counterpart persona not found",
        "Session not found",
        "Coach prompt not found",
        "Counterpart prompt not found",
        "Evaluator prompt not found",
    }:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
    ) from exc

### ----------------------- SIMULATION CREATE ---------------------- ###
@router.post(
    "/",
    response_model=SimulationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_simulation(
    simulation_data: SimulationCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> SimulationRead:
    """
    Create a new simulation.
    Args:
        simulation_data: The data for creating the simulation.
        session: The database session.
        current_user: The user creating the simulation.
    Returns:
        A SimulationRead containing the created simulation.
    Raises:
        ValueError: If the simulation cannot be created.
    """
    try:
        return await simulations_service.create_simulation_srvc(
            simulation_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_simulation_service_error(exc)


@router.get(
    "/",
    response_model=list[SimulationRead],
    status_code=status.HTTP_200_OK,
)
async def list_simulations(
    session: SessionDep,
    current_user: CurrentUserDep,
    page: Page,
    status: SimulationStatus | None = None,
    owner_id: int | None = None,
    participant_id: int | None = None,
    teacher_id: int | None = None,
    corpus_id: int | None = None,
    corpus_index_id: int | None = None,
    coach_prompt_id: int | None = None,
    counterpart_prompt_id: int | None = None,
    evaluator_prompt_id: int | None = None,
    session_id: int | None = None,
    scenario_id: int | None = None,
) -> list[SimulationRead]:
    return await simulations_service.list_simulations_srvc(
        session=session,
        skip=page["skip"],
        limit=page["limit"],
        status=status,
        owner_id=owner_id,
        participant_id=participant_id,
        teacher_id=teacher_id,
        corpus_id=corpus_id,
        corpus_index_id=corpus_index_id,
        coach_prompt_id=coach_prompt_id,
        counterpart_prompt_id=counterpart_prompt_id,
        evaluator_prompt_id=evaluator_prompt_id,
        session_id=session_id,
        scenario_id=scenario_id,
        current_user=current_user,
    )

### -------------------- LIST REVIEWED SIMULATIONS ----------------- ###
@router.get(
    "/reviews",
    response_model=SimulationEvaluationListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_reviewed_simulations(
    session: SessionDep,
    current_user: TeacherOrAdminDep,
    page: Page,
) -> SimulationEvaluationListResponse:
    return await simulations_service.list_reviewed_simulations_srvc(
        session,
        current_user=current_user,
        skip=page["skip"],
        limit=page["limit"],
    )

### -------------------- LIST COMPLETED SIMULATIONS ---------------- ###
@router.get(
    "/completed",
    response_model=SimulationEvaluationListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_completed_simulations(
    session: SessionDep,
    current_user: TeacherOrAdminDep,
    page: Page,
) -> SimulationEvaluationListResponse:
    return await simulations_service.list_completed_simulations_srvc(
        session,
        current_user=current_user,
        skip=page["skip"],
        limit=page["limit"],
    )

### --------------------- GET SIMULATION BY ID --------------------- ###
@router.get(
    "/{simulation_id}",
    response_model=SimulationReadWithState,
    status_code=status.HTTP_200_OK,
)
async def get_simulation(
    simulation: ReadableSimulationDep,
) -> SimulationReadWithState:
    """
    Get a simulation by its ID.
    Args:
        simulation: The simulation instance.
    Returns:
        A SimulationReadWithState containing the simulation data.
    """
    return await simulations_service.get_simulation_srvc(simulation)

### -------------------- UPDATE SIMULATION BY ID ------------------- ###
@router.patch(
    "/{simulation_id}",
    response_model=SimulationRead,
    status_code=status.HTTP_200_OK,
)
async def update_simulation(
    simulation_data: SimulationUpdateRequest,
    simulation: AccessibleSimulationDep,
    session: SessionDep,
) -> SimulationRead:
    """
    Update a simulation by its ID.
    Args:
        simulation_data: The data for updating the simulation.
        simulation: The simulation instance.
        session: The database session.
    Returns:
        A SimulationRead containing the updated simulation.
    Raises:
        ValueError: If the simulation cannot be updated.
    """
    try:
        return await simulations_service.update_simulation_srvc(
            simulation,
            simulation_data,
            session,
        )
    except ValueError as exc:
        _raise_simulation_service_error(exc)

### -------------------- DELETE SIMULATION BY ID ------------------- ###
@router.delete(
    "/{simulation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_simulation(
    simulation: AccessibleSimulationDep,
    session: SessionDep,
) -> None:
    """
    Delete a simulation by its ID.
    Args:
        simulation: The simulation instance.
        session: The database session.
    Returns:
        None
    Raises:
        ValueError: If the simulation cannot be deleted.
    """
    try:
        await simulations_service.delete_simulation_srvc(simulation, session)
    except ValueError as exc:
        _raise_simulation_service_error(exc)

### ------------------------ SIMULATION START ---------------------- ###
@router.post(
    "/{simulation_id}/start",
    response_model=SimulationReadWithState,
    status_code=status.HTTP_200_OK,
)
async def start_simulation(
    start_data: SimulationStartRequest,
    simulation: AccessibleSimulationDep,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> SimulationReadWithState:
    """
    Start a simulation.
    Args:
        start_data: The data for starting the simulation.
        simulation: The simulation instance.
        session: The database session.
        current_user: The user starting the simulation.
    Returns:
        A SimulationReadWithState containing the updated simulation state.
    Raises:
        ValueError: If the simulation cannot be started.
    """
    try:
        return await simulations_service.start_simulation_srvc(
            simulation,
            start_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_simulation_service_error(exc)

### ------------------------ SIMULATION TURN ----------------------- ###
@router.post(
    "/{simulation_id}/turn",
    response_model=SimulationTurnResponse,
    status_code=status.HTTP_200_OK,
)
async def submit_simulation_turn(
    turn_data: SimulationTurnRequest,
    simulation: AccessibleSimulationDep,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> SimulationTurnResponse:
    """
    Submit a turn for a simulation.
    Args:
        turn_data: The data for the simulation turn.
        simulation: The simulation instance.
        session: The database session.
        current_user: The user submitting the turn.
    Returns:
        A SimulationTurnResponse containing the result of the turn.
    Raises:
        ValueError: If the turn cannot be submitted.
    """
    try:
        return await simulations_service.submit_simulation_turn_srvc(
            simulation,
            turn_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_simulation_service_error(exc)

### --------------------- SIMULATION PROXY TURN -------------------- ###
@router.post(
    "/{simulation_id}/proxy-turn",
    response_model=SimulationProxyTurnResponse,
    status_code=status.HTTP_200_OK,
)
async def submit_simulation_proxy_turn(
    proxy_data: SimulationProxyTurnRequest,
    simulation: AccessibleSimulationDep,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> SimulationProxyTurnResponse:
    """
    Submit a proxy turn for a simulation.
    Args:
        proxy_data: The data for the proxy turn.
        simulation: The simulation instance.
        session: The database session.
        current_user: The user submitting the proxy turn.
    Returns:
        A SimulationProxyTurnResponse containing the result of the 
        proxy turn.
    Raises:
        ValueError: If the proxy turn cannot be submitted.
    """
    try:
        return await simulations_service.submit_simulation_proxy_turn_srvc(
            simulation,
            proxy_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_simulation_service_error(exc)

### --------------------------  PROXY DISABLE ---------------------- ###
@router.post(
    "/{simulation_id}/proxy/disable",
    response_model=SimulationProxyDisableResponse,
    status_code=status.HTTP_200_OK,
)
async def disable_simulation_proxy(
    simulation: AccessibleSimulationDep,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> SimulationProxyDisableResponse:
    """
    Disable the proxy for a simulation.
    Args:
        simulation: The simulation instance.
        session: The database session.
        current_user: The user disabling the proxy.
    Returns:
        A SimulationProxyDisableResponse containing the result of the 
        proxy disable action.
    Raises:
        ValueError: If the proxy cannot be disabled.
    """
    try:
        return await simulations_service.disable_simulation_proxy_srvc(
            simulation,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_simulation_service_error(exc)

### ---------------------- GET SIMULATION STATE -------------------- ###
@router.get(
    "/{simulation_id}/state",
    response_model=SimulationReadWithState,
    status_code=status.HTTP_200_OK,
)
async def get_simulation_state(
    simulation: ReadableSimulationDep,
) -> SimulationReadWithState:
    """
    Get the current state of a simulation.
    Args:
        simulation: The simulation instance.
    Returns:
        A SimulationReadWithState containing the current simulation state.
    Raises:
        ValueError: If the simulation state cannot be retrieved.
    """
    return await simulations_service.get_simulation_state_srvc(simulation)

### -------------------- CANCEL SIMULATION BY ID ------------------- ###
@router.post(
    "/{simulation_id}/cancel",
    response_model=SimulationRead,
    status_code=status.HTTP_200_OK,
)
async def cancel_simulation(
    simulation: AccessibleSimulationDep,
    session: SessionDep,
) -> SimulationRead:
    """
    Cancel a simulation by its ID.
    Args:
        simulation: The simulation instance.
        session: The database session.
    Returns:
        A SimulationRead containing the updated simulation.
    """
    try:
        return await simulations_service.cancel_simulation_srvc(simulation, session)
    except ValueError as exc:
        _raise_simulation_service_error(exc)


### -------------------- TEACHER REVIEW SIMULATION ----------------- ###
@router.post(
    "/{simulation_id}/review",
    response_model=SimulationRead,
    status_code=status.HTTP_200_OK,
)
async def review_simulation(
    review_data: SimulationTeacherReviewRequest,
    simulation: TeacherReviewSimulationDep,
    session: SessionDep,
    current_teacher: CurrentUserDep,
) -> SimulationRead:
    """
    Review a simulation as a teacher.
    Args:
        review_data: The data for the teacher review, including feedback.
        simulation: The simulation instance to review.
        session: The database session.
        current_teacher: The teacher submitting the review.
    Returns:
        A SimulationRead containing the updated simulation with the review.
    Raises:
        ValueError: If the current user is not a teacher or if the review 
        cannot be submitted due to the simulation's current status.
    """
    try:
        return await simulations_service.review_simulation_srvc(
            simulation,
            review_data,
            session,
            current_teacher,
        )
    except ValueError as exc:
        _raise_simulation_service_error(exc)

### ------------------- UPDATE TEACHER REVIEW SIMULATION ----------- ###
@router.patch(
    "/{simulation_id}/review",
    response_model=SimulationRead,
    status_code=status.HTTP_200_OK,
)
async def update_review_simulation(
    review_data: SimulationTeacherReviewRequest,
    simulation: TeacherReviewSimulationDep,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> SimulationRead:
    try:
        return await simulations_service.update_review_simulation_srvc(
            simulation,
            review_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_simulation_service_error(exc)

### ------------------- DELETE TEACHER REVIEW SIMULATION ----------- ###
@router.delete(
    "/{simulation_id}/review",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_review_simulation(
    simulation: TeacherReviewSimulationDep,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> None:
    try:
        await simulations_service.delete_review_simulation_srvc(
            simulation,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_simulation_service_error(exc)
