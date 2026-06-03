from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.documents import Document
from sqlmodel.ext.asyncio.session import AsyncSession

from airag.chains.negotiation.negotiation import make_negotiation_graph
from models.simulations import Simulation
from models.users import User
from repositories import simulations_repo
from schemas.simulations_schemas import (
    NegotiationStateSchema,
    SimulationCreate,
    SimulationCreateRequest,
    SimulationMessageSchema,
    SimulationRead,
    SimulationReadWithState,
    SimulationStatus,
    SimulationStatusUpdate,
    SimulationTurnRequest,
    SimulationTurnResponse,
    SimulationUpdate,
    SimulationUpdateRequest,
    SimulationStartRequest,
)


TERMINAL_STATUSES = {"completed", "cancelled", "failed"}
RUNNABLE_STATUSES = {"active", "paused"}

# CHECK the lru_cache usage here, sus
@lru_cache
def get_compiled_negotiation_graph():
    """Compile the negotiation graph once per process."""
    return make_negotiation_graph()

# Candidate for helpers module
def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()

# Candidate for helpers module
def _json_safe(value: Any) -> Any:
    """
    Ensure that a value is JSON serializable by converting known complex types to
    simpler representations. This is used to safely include complex data in the
    negotiation state and messages without risking serialization errors.
    The function handles BaseMessage and Document types from langchain, as well as
    any object with a model_dump method (like Pydantic models). For other types,
    it falls back to converting the value to a string.
    """
    if isinstance(value, BaseMessage):
        return {
            "role": value.type,
            "content": str(value.content),
            "metadata": dict(value.additional_kwargs),
        }
    if isinstance(value, Document):
        return {
            "page_content": value.page_content,
            "metadata": dict(value.metadata),
        }
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    return str(value)


def _message_to_schema(message: Any) -> SimulationMessageSchema:
    """
    Convert a message in various possible formats to a SimulationMessageSchema. 
    This function handles SimulationMessageSchema, BaseMessage, and dict types,
    ensuring that the resulting schema is JSON serializable and contains the
    necessary fields for the negotiation messages.
    """
    if isinstance(message, SimulationMessageSchema):
        return message

    if isinstance(message, BaseMessage):
        return SimulationMessageSchema(
            role=message.type,
            content=str(message.content),
            timestamp=message.additional_kwargs.get("timestamp"),
            metadata={
                key: _json_safe(value)
                for key, value in message.additional_kwargs.items()
                if key != "timestamp"
            },
        )

    if isinstance(message, dict):
        metadata = message.get("metadata") or {}
        for key in ("side", "sender", "name"):
            if key in message and key not in metadata:
                metadata[key] = message[key]
        return SimulationMessageSchema(
            role=str(message.get("role") or message.get("type") or "assistant"),
            content=str(message.get("content") or message.get("raw_text") or ""),
            timestamp=message.get("timestamp"),
            metadata=_json_safe(metadata),
        )

    return SimulationMessageSchema(role="assistant", content=str(message))


def _read_simulation(simulation: Simulation) -> SimulationRead:
    """
    Convert a Simulation model instance to a SimulationRead schema.
    This function extracts the relevant fields from the Simulation model
    and returns a SimulationRead schema instance.
    """
    return SimulationRead(
        id=simulation.id,
        name=simulation.name,
        description=simulation.description,
        status=simulation.status,
        session_id=simulation.session_id,
        user_id_owner=simulation.user_id_owner,
        user_id_participant=simulation.user_id_participant,
        scenario_id=simulation.scenario_id,
        corpus_id=simulation.corpus_id,
        counter_part_side_persona_id=simulation.counter_part_side_persona_id,
        user_side=simulation.user_side,
        teacher_reviewed=simulation.teacher_reviewed,
        teacher_id=simulation.teacher_id,
        teacher_feedback=simulation.teacher_feedback,
        reviewed_at=simulation.reviewed_at,
        created_at=simulation.created_at,
        last_updated=simulation.last_updated,
    )


def _read_simulation_with_state(simulation: Simulation) -> SimulationReadWithState:
    """
    Convert a Simulation model instance to a SimulationReadWithState schema.
    This function extracts the relevant fields from the Simulation model,
    including the negotiation state and messages, and returns a 
    SimulationReadWithState schema instance.
    """
    base = _read_simulation(simulation).model_dump()
    raw_state = simulation.negotiation_state or {}
    raw_messages = simulation.messages or []
    return SimulationReadWithState(
        **base,
        negotiation_state=NegotiationStateSchema.model_validate(raw_state),
        messages=[_message_to_schema(message) for message in raw_messages],
    )

# Candidate for helpers module
def _has_role(user: User, role_name: str) -> bool:
    """
    Check if a user has a specific role.
    Args:
        user: The user to check.
        role_name: The name of the role to check for.
    Returns:
        True if the user has the role, False otherwise.
    """
    return any(getattr(role, "name", None) == role_name for role in getattr(user, "roles", []))


def _is_simulation_accessible_to_user(simulation: Simulation, user: User) -> bool:
    """
    Determine if a simulation is accessible to a user based on their role and
    their relationship to the simulation.
    Args:
        simulation: The simulation to check access for.
        user: The user for whom to check access.
    Returns:
        True if the simulation is accessible to the user, False otherwise.
    """
    if _has_role(user, "admin"):
        return True

    return user.id in {
        simulation.user_id_owner,
        simulation.user_id_participant,
        simulation.teacher_id,
    }


def _initial_graph_state(
    simulation: Simulation,
    start_data: SimulationStartRequest,
    current_user: User,
) -> dict[str, Any]:
    """
    Initialize the graph state for a simulation.
    Args:
        simulation: The simulation for which to initialize the state.
        start_data: The data provided to start the simulation.
        current_user: The user who is starting the simulation.
    Returns:
        A dictionary representing the initial graph state.
    """
    phase = "opening" if start_data.side_a and start_data.side_b else "setup"
    state: dict[str, Any] = {
        "session_id": str(simulation.id),
        "user_id": str(current_user.id),
        "user_side": simulation.user_side or "side_a",
        "side_a": _json_safe(start_data.side_a),
        "side_b": _json_safe(start_data.side_b),
        "messages": [],
        "phase": phase,
        "active_side": simulation.user_side or "side_a",
        "offer_history": [],
        "turn_count": 0,
        "event_log": ["api:simulation_started"],
        "max_turn_count": start_data.max_turn_count,
    }

    if start_data.opening_message:
        state["messages"].append(
            {
                "role": "user",
                "content": start_data.opening_message,
                "timestamp": _utc_timestamp(),
                "side": state["user_side"],
            }
        )

    return state


def _state_schema_from_graph_state(state: dict[str, Any]) -> NegotiationStateSchema:
    """
    Convert a graph state dictionary to a NegotiationStateSchema.
    Args:
        state: The graph state dictionary.
    Returns:
        A NegotiationStateSchema instance representing the state.
    """
    return NegotiationStateSchema(
        current_phase=state.get("phase"),
        user_side=state.get("user_side"),
        data=_json_safe(state),
    )


def _messages_from_graph_state(state: dict[str, Any]) -> list[SimulationMessageSchema]:
    """
    Convert messages from a graph state dictionary to a list of SimulationMessageSchema.
    Args:
        state: The graph state dictionary.
    Returns:
        A list of SimulationMessageSchema instances.
    """
    return [_message_to_schema(message) for message in state.get("messages", [])]


def _graph_state_from_simulation(simulation: Simulation) -> dict[str, Any]:
    """
    Convert a simulation instance to a graph state dictionary.
    Args:
        simulation: The simulation instance.
    Returns:
        A dictionary representing the graph state.
    """
    raw_state = simulation.negotiation_state or {}
    data = raw_state.get("data", {}) if isinstance(raw_state, dict) else {}
    state = dict(data)
    state.setdefault("session_id", str(simulation.id))
    state.setdefault("user_id", str(simulation.user_id_owner))
    state.setdefault("user_side", simulation.user_side or raw_state.get("user_side") or "side_a")
    state.setdefault("messages", [])
    state.setdefault("offer_history", [])
    state.setdefault("event_log", [])
    if raw_state.get("current_phase"):
        state.setdefault("phase", raw_state["current_phase"])
    return state


def _user_message(turn_data: SimulationTurnRequest, simulation: Simulation) -> dict[str, Any]:
    """
    Create a user message dictionary from turn data and simulation.
    Args:
        turn_data: The data for the current turn.
        simulation: The simulation instance.
    Returns:
        A dictionary representing the user message.
    """
    message = {
        "role": "user",
        "content": turn_data.message,
        "timestamp": _utc_timestamp(),
        "side": simulation.user_side or "side_a",
    }
    if turn_data.current_offer:
        message["current_offer"] = _json_safe(turn_data.current_offer)
    return message


def _status_after_graph(graph_state: dict[str, Any]) -> SimulationStatus:
    """
    Determine the status of a simulation based on its graph state.
    Args:
        graph_state: The graph state dictionary.
    Returns:
        The status of the simulation.
    """
    if graph_state.get("phase") == "ended" or graph_state.get("next_action") == "end":
        return "completed"
    if graph_state.get("should_pause"):
        return "paused"
    return "active"


def _counterpart_response(graph_state: dict[str, Any], user_side: str | None) -> str | None:
    """
    Get the counterpart's response from the graph state.
    Args:
        graph_state: The graph state dictionary.
        user_side: The side of the current user.
    Returns:
        The counterpart's response, if available.
    """
    counterpart_key = "side_b_response" if user_side == "side_a" else "side_a_response"
    return graph_state.get(counterpart_key) or graph_state.get("side_a_response") or graph_state.get("side_b_response")


async def create_simulation_srvc(
    simulation_data: SimulationCreateRequest,
    session: AsyncSession,
    current_user: User,
) -> SimulationRead:
    """
    Create a new simulation.
    Args:
        simulation_data: The data for creating the simulation.
        session: The database session.
        current_user: The user creating the simulation.
    Returns:
        The created simulation.
    """
    simulation_in = SimulationCreate(
        **simulation_data.model_dump(),
        user_id_owner=current_user.id,
    )
    simulation = await simulations_repo.create_simulation(simulation_in, session)
    return _read_simulation(simulation)


async def list_simulations_srvc(
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
    current_user: User | None = None,
) -> list[SimulationRead]:
    """
    List simulations based on various filters.
    Args:
        session: The database session.
        skip: The number of simulations to skip.
        limit: The maximum number of simulations to return.
        status: The status of the simulations to filter by.
        owner_id: The ID of the owner to filter by.
        participant_id: The ID of the participant to filter by.
        teacher_id: The ID of the teacher to filter by.
        corpus_id: The ID of the corpus to filter by.
        session_id: The ID of the session to filter by.
        scenario_id: The ID of the scenario to filter by.
        current_user: The current user making the request.
    Returns:
        A list of simulations matching the filters.
    """
    simulations = await simulations_repo.list_simulations(
        session=session,
        skip=skip,
        limit=limit,
        status=status,
        owner_id=owner_id,
        participant_id=participant_id,
        teacher_id=teacher_id,
        corpus_id=corpus_id,
        session_id=session_id,
        scenario_id=scenario_id,
    )
    if current_user is not None:
        simulations = [
            simulation
            for simulation in simulations
            if _is_simulation_accessible_to_user(simulation, current_user)
        ]

    return [_read_simulation(simulation) for simulation in simulations]


async def get_simulation_srvc(simulation: Simulation) -> SimulationReadWithState:
    """
    Get a simulation with its state.
    Args:
        simulation: The simulation instance.
    Returns:
        The simulation with its state.
    """
    return _read_simulation_with_state(simulation)

# CHECK
async def update_simulation_srvc(
    simulation: Simulation,
    simulation_data: SimulationUpdateRequest,
    session: AsyncSession,
) -> SimulationRead:
    """
    Update a simulation.
    Args:
        simulation: The simulation instance.
        simulation_data: The data for updating the simulation.
        session: The database session.
    Returns:
        The updated simulation.
    """
    simulation_in = SimulationUpdate(**simulation_data.model_dump(exclude_unset=True))
    updated_simulation = await simulations_repo.update_simulation(
        simulation,
        simulation_in,
        session,
    )
    return _read_simulation(updated_simulation)


async def delete_simulation_srvc(
    simulation: Simulation,
    session: AsyncSession,
) -> None:
    """
    Delete a simulation.
    Args:
        simulation: The simulation instance.
        session: The database session.
    Returns:
        None
    """
    if simulation.status == "created":
        await simulations_repo.delete_simulation(simulation, session)
        return

    if simulation.status in TERMINAL_STATUSES:
        raise ValueError("Ended simulations cannot be deleted here")

    await simulations_repo.update_simulation_status(
        simulation,
        SimulationStatusUpdate(status="cancelled"),
        session,
    )


async def start_simulation_srvc(
    simulation: Simulation,
    start_data: SimulationStartRequest,
    session: AsyncSession,
    current_user: User,
) -> SimulationReadWithState:
    """
    Start a simulation, initializing its state and setting it to active.
    Args:
        simulation: The simulation instance to start.
        start_data: The data required to start the simulation.
        session: The database session.
        current_user: The user starting the simulation.
    Returns:
        The started simulation with its initial state.
    Raises:
        ValueError: If the simulation cannot be started due to its 
        current status.
    """
    if simulation.status != "created":
        raise ValueError("Only created simulations can be started")

    state = _initial_graph_state(simulation, start_data, current_user)
    update_in = SimulationUpdate(
        status="active",
        negotiation_state=_state_schema_from_graph_state(state),
        messages=_messages_from_graph_state(state),
    )
    updated_simulation = await simulations_repo.update_simulation(
        simulation,
        update_in,
        session,
    )
    return _read_simulation_with_state(updated_simulation)


async def submit_simulation_turn_srvc(
    simulation: Simulation,
    turn_data: SimulationTurnRequest,
    session: AsyncSession,
    current_user: User,
    negotiation_graph: Any | None = None,
) -> SimulationTurnResponse:
    """
    Submit a simulation turn, process user input, update negotiation state
    and determine the next status of the simulation.
    Args:
        simulation: The simulation instance.
        turn_data: The data for the current turn, including user message and 
        optional current offer.
        session: The database session.
        current_user: The user submitting the turn.
        negotiation_graph: An optional pre-compiled negotiation graph to use 
        for processing the turn. If not provided, the default graph will be 
        used.
    Returns:
        A SimulationTurnResponse containing the updated simulation state and 
        any relevant information for the next turn.
    Raises:
        ValueError: If the simulation is not in a state that allows 
        submitting a turn.
    """
    if simulation.status not in RUNNABLE_STATUSES:
        raise ValueError("Simulation must be active or paused to submit a turn")

    state = _graph_state_from_simulation(simulation)
    state["user_id"] = str(current_user.id)
    state["user_side"] = simulation.user_side or state.get("user_side") or "side_a"
    state.setdefault("messages", [])
    state["messages"] = [*state["messages"], _user_message(turn_data, simulation)]
    if turn_data.current_offer:
        state["current_offer"] = _json_safe(turn_data.current_offer)

    graph = negotiation_graph or get_compiled_negotiation_graph()
    graph_state = _json_safe(graph.invoke(state))
    next_status = _status_after_graph(graph_state)
    update_in = SimulationUpdate(
        status=next_status,
        negotiation_state=_state_schema_from_graph_state(graph_state),
        messages=_messages_from_graph_state(graph_state),
    )
    updated_simulation = await simulations_repo.update_simulation(
        simulation,
        update_in,
        session,
    )

    return SimulationTurnResponse(
        simulation_id=updated_simulation.id,
        status=next_status,
        phase=graph_state.get("phase"),
        should_pause=bool(graph_state.get("should_pause", False)),
        pause_reason=graph_state.get("pause_reason") or None,
        messages=_messages_from_graph_state(graph_state),
        coach_advice=graph_state.get("coach_advice") or {},
        counterpart_response=_counterpart_response(graph_state, state.get("user_side")),
        event_log=graph_state.get("event_log") or [],
    )


async def get_simulation_state_srvc(simulation: Simulation) -> SimulationReadWithState:
    """
    Get the current state of a simulation.
    Args:
        simulation: The simulation instance.
    Returns:
        A SimulationReadWithState containing the current state of the 
        simulation.
    """
    return _read_simulation_with_state(simulation)


async def cancel_simulation_srvc(
    simulation: Simulation,
    session: AsyncSession,
) -> SimulationRead:
    """
    Cancel a simulation.
    Args:
        simulation: The simulation instance.
        session: The database session.
    Returns:
        A SimulationRead containing the updated simulation state.
    Raises:
        ValueError: If the simulation is not in a state that allows 
        cancellation.
    """
    if simulation.status not in {"created", "active", "paused"}:
        raise ValueError("Only created, active, or paused simulations can be cancelled")

    updated_simulation = await simulations_repo.update_simulation_status(
        simulation,
        SimulationStatusUpdate(status="cancelled"),
        session,
    )
    return _read_simulation(updated_simulation)
