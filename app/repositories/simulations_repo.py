from datetime import datetime, timezone

from models.simulations import Simulation
from schemas.simulations_schemas import (
    SimulationCreate,
    SimulationMessageAppend,
    SimulationMessagesReplace,
    SimulationNegotiationStateUpdate,
    SimulationStatus,
    SimulationStatusUpdate,
    SimulationTeacherReview,
    SimulationUpdate,
)
from repositories.helpers import commit_and_refresh, commit_delete, utc_now
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "created": {"active", "cancelled"},
    "active": {"paused", "completed", "cancelled", "failed"},
    "paused": {"active", "cancelled", "failed"},
    "completed": set(),
    "cancelled": set(),
    "failed": set(),
}

def _set_last_updated(simulation: Simulation) -> None:
    simulation.last_updated = utc_now()


def _validate_status_transition(current_status: str, next_status: SimulationStatus) -> None:
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
    session_id: int | None = None,
    scenario_id: int | None = None,
) -> list[Simulation]:
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
    simulation = Simulation(**simulation_in.model_dump())
    return await commit_and_refresh(session, simulation)


async def update_simulation(
    simulation: Simulation,
    simulation_in: SimulationUpdate,
    session: AsyncSession,
) -> Simulation:
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
    _validate_status_transition(simulation.status, status_in.status)
    simulation.status = status_in.status
    _set_last_updated(simulation)
    return await commit_and_refresh(session, simulation)


async def append_simulation_message(
    simulation: Simulation,
    message_in: SimulationMessageAppend,
    session: AsyncSession,
) -> Simulation:
    simulation.messages = [*simulation.messages, message_in.message.model_dump()]
    _set_last_updated(simulation)
    return await commit_and_refresh(session, simulation)


async def replace_simulation_messages(
    simulation: Simulation,
    messages_in: SimulationMessagesReplace,
    session: AsyncSession,
) -> Simulation:
    simulation.messages = [message.model_dump() for message in messages_in.messages]
    _set_last_updated(simulation)
    return await commit_and_refresh(session, simulation)


async def update_negotiation_state(
    simulation: Simulation,
    state_in: SimulationNegotiationStateUpdate,
    session: AsyncSession,
) -> Simulation:
    simulation.negotiation_state = state_in.negotiation_state.model_dump()
    _set_last_updated(simulation)
    return await commit_and_refresh(session, simulation)


async def review_simulation(
    simulation: Simulation,
    review_in: SimulationTeacherReview,
    session: AsyncSession,
) -> Simulation:
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
    await commit_delete(session, simulation)