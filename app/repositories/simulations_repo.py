from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# local imports
from app.models.simulations import Simulation
from app.schemas.simulations_schemas import (
    SimulationCreate,
    SimulationMessageAppend,
    SimulationMessagesReplace,
    SimulationNegotiationStateUpdate,
    SimulationStatus,
    SimulationStatusUpdate,
    SimulationTeacherReview,
    SimulationUpdate,
)
from app.repositories.helpers import commit_and_refresh, commit_delete, utc_now

ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "created": {"active", "cancelled"},
    "active": {"paused", "completed", "cancelled", "failed"},
    "paused": {"active", "completed", "cancelled", "failed"},
    "completed": set(),
    "cancelled": set(),
    "failed": set(),
}

def _set_last_updated(simulation: Simulation) -> None:
    """
    Update the last_updated field of a simulation to the current UTC time.
        Args:
            simulation: The simulation to update.
        Returns:
            None
    """
    simulation.last_updated = utc_now()


def _validate_status_transition(current_status: str, next_status: SimulationStatus) -> None:
    """
    Validate the transition from the current status to the next status.
        Args:
            current_status: The current status of the simulation.
            next_status: The desired next status of the simulation.
        Returns:
            None
        Raises:
            ValueError: If the transition is not allowed.
    """
    if next_status == current_status:
        return

    allowed_next_statuses = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
    if next_status not in allowed_next_statuses:
        raise ValueError(
            f"Invalid simulation status transition: {current_status!r} -> {next_status!r}"
        )


async def get_simulation_by_id(
    simulation_id: int,
    session: AsyncSession,
) -> Simulation | None:
    """
    Get a simulation by its ID.
        Args:
            simulation_id: The ID of the simulation to retrieve.
            session: The database session.
        Returns:
            The Simulation instance if found, else None.
    """
    return await session.get(Simulation, simulation_id)


async def list_simulations(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
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
) -> list[Simulation]:
    """
    List simulations with optional filters.
        Args:
            session: The database session.
            skip: Number of records to skip.
            limit: Maximum number of records to return.
            status: Optional status filter.
            owner_id: Optional owner ID filter.
            participant_id: Optional participant ID filter.
            teacher_id: Optional teacher ID filter.
            corpus_id: Optional corpus ID filter.
            corpus_index_id: Optional corpus index ID filter.
            coach_prompt_id: Optional coach prompt ID filter.
            counterpart_prompt_id: Optional counterpart prompt ID filter.
            evaluator_prompt_id: Optional evaluator prompt ID filter.
            session_id: Optional session ID filter.
            scenario_id: Optional scenario ID filter.
        Returns:
            A list of Simulation instances.
    """
    statement = select(Simulation)

    if status is not None:
        statement = statement.where(Simulation.status == status)
    if owner_id is not None:
        statement = statement.where(Simulation.user_id_owner == owner_id)
    if participant_id is not None:
        statement = statement.where(Simulation.user_id_participant == participant_id)
    if teacher_id is not None:
        statement = statement.where(Simulation.teacher_id == teacher_id)
    if corpus_id is not None:
        statement = statement.where(Simulation.corpus_id == corpus_id)
    if corpus_index_id is not None:
        statement = statement.where(Simulation.corpus_index_id == corpus_index_id)
    if coach_prompt_id is not None:
        statement = statement.where(Simulation.coach_prompt_id == coach_prompt_id)
    if counterpart_prompt_id is not None:
        statement = statement.where(Simulation.counterpart_prompt_id == counterpart_prompt_id)
    if evaluator_prompt_id is not None:
        statement = statement.where(Simulation.evaluator_prompt_id == evaluator_prompt_id)
    if session_id is not None:
        statement = statement.where(Simulation.session_id == session_id)
    if scenario_id is not None:
        statement = statement.where(Simulation.scenario_id == scenario_id)

    statement = statement.offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def create_simulation(
    simulation_in: SimulationCreate,
    session: AsyncSession,
) -> Simulation:
    """
    Create a new simulation.
        Args:
            simulation_in: The simulation data to create.
            session: The database session.
        Returns:
            The created Simulation instance.
    """
    simulation = Simulation(**simulation_in.model_dump())
    return await commit_and_refresh(session, simulation)


async def update_simulation(
    simulation: Simulation,
    simulation_in: SimulationUpdate,
    session: AsyncSession,
) -> Simulation:
    # TODO: Probably abandon; there is no logic in updating a simulation
    # outside itself.
    """
    Update an existing simulation.
    Args:
        simulation: The simulation to update.
        simulation_in: The simulation data to update.
        session: The database session.
    Returns:
        The updated Simulation instance.
    """
    update_data = simulation_in.model_dump(exclude_unset=True)

    if "negotiation_state" in update_data and update_data["negotiation_state"] is not None:
        update_data["negotiation_state"] = simulation_in.negotiation_state.model_dump()

    if "messages" in update_data and update_data["messages"] is not None:
        update_data["messages"] = [message.model_dump() for message in simulation_in.messages]

    if "status" in update_data and update_data["status"] is not None:
        _validate_status_transition(simulation.status, update_data["status"])

    for field_name, value in update_data.items():
        setattr(simulation, field_name, value)

    _set_last_updated(simulation)
    return await commit_and_refresh(session, simulation)


async def update_simulation_status(
    simulation: Simulation,
    status_in: SimulationStatusUpdate,
    session: AsyncSession,
) -> Simulation:
    """
    Update the status of an existing simulation.
    Args:
        simulation: The simulation to update.
        status_in: The new status data.
        session: The database session.
    Returns:
        The updated Simulation instance.
    """
    _validate_status_transition(simulation.status, status_in.status)
    simulation.status = status_in.status
    _set_last_updated(simulation)
    return await commit_and_refresh(session, simulation)


async def append_simulation_message(
    simulation: Simulation,
    message_in: SimulationMessageAppend,
    session: AsyncSession,
) -> Simulation:
    """
    Append a message to an existing simulation.
    Args:
        simulation: The simulation to update.
        message_in: The message data to append.
        session: The database session.
    Returns:
        The updated Simulation instance.
    """
    simulation.messages = [*simulation.messages, message_in.message.model_dump()]
    _set_last_updated(simulation)
    return await commit_and_refresh(session, simulation)


async def replace_simulation_messages(
    simulation: Simulation,
    messages_in: SimulationMessagesReplace,
    session: AsyncSession,
) -> Simulation:
    """
    Replace the messages of an existing simulation.
    Args:
        simulation: The simulation to update.
        messages_in: The new messages data.
        session: The database session.
    Returns:
        The updated Simulation instance.
    """
    simulation.messages = [message.model_dump() for message in messages_in.messages]
    _set_last_updated(simulation)
    return await commit_and_refresh(session, simulation)


async def update_negotiation_state(
    simulation: Simulation,
    state_in: SimulationNegotiationStateUpdate,
    session: AsyncSession,
) -> Simulation:
    """
    Update the negotiation state of an existing simulation.
    Args:
        simulation: The simulation to update.
        state_in: The new negotiation state data.
        session: The database session.
    Returns:
        The updated Simulation instance.
    """
    simulation.negotiation_state = state_in.negotiation_state.model_dump()
    _set_last_updated(simulation)
    return await commit_and_refresh(session, simulation)


async def review_simulation(
    simulation: Simulation,
    review_in: SimulationTeacherReview,
    session: AsyncSession,
) -> Simulation:
    """
    Review an existing simulation.
    Args:
        simulation: The simulation to review.
        review_in: The review data.
        session: The database session.
    Returns:
        The updated Simulation instance.
    """
    if not review_in.teacher_feedback or not review_in.teacher_feedback.strip():
        raise ValueError("Teacher feedback is required")

    simulation.teacher_id = review_in.teacher_id
    simulation.teacher_feedback = review_in.teacher_feedback
    simulation.teacher_reviewed = True
    simulation.reviewed_at = review_in.reviewed_at or utc_now()
    _set_last_updated(simulation)
    return await commit_and_refresh(session, simulation)

async def delete_simulation(
    simulation: Simulation,
    session: AsyncSession,
) -> None:
    """
    Delete an existing simulation.
    Args:
        simulation: The simulation to delete.
        session: The database session.
    Returns:
        None"""
    await commit_delete(session, simulation)
