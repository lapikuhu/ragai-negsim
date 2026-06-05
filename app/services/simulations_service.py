from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.documents import Document
from sqlmodel.ext.asyncio.session import AsyncSession

from app.airag.chains.negotiation.negotiation import make_negotiation_graph
from app.airag.embeddings.embeddings import choose_embedding_model
from app.airag.retrieval.retrievers import make_dense_retriever
from app.airag.vector_stores.vector_stores import (
    instantiate_chroma_vector_store,
    instantiate_pgvector_store,
    load_faiss_vector_store,
)
from app.models.simulations import Simulation
from app.models.users import User
from app.repositories import (
    counterpart_personas_repo,
    corpus_indices_repo,
    corpus_repo,
    prompts_repo,
    scenarios_repo,
    sessions_repo,
    simulations_repo,
    vector_stores_repo,
)
from app.schemas.simulations_schemas import (
    NegotiationStateSchema,
    SimulationCreate,
    SimulationCreateRequest,
    SimulationMessageSchema,
    SimulationRead,
    SimulationReadWithState,
    SimulationStatus,
    SimulationStatusUpdate,
    SimulationTeacherReview,
    SimulationTeacherReviewRequest,
    SimulationTurnRequest,
    SimulationTurnResponse,
    SimulationUpdate,
    SimulationUpdateRequest,
    SimulationStartRequest,
)


TERMINAL_STATUSES = {"completed", "cancelled", "failed"}
RUNNABLE_STATUSES = {"active", "paused"}
NEGOTIATION_GRAPH_CACHE: dict[tuple[Any, ...], Any] = {}


@dataclass(frozen=True)
class SimulationRuntimeContext:
    corpus: Any | None = None
    corpus_index: Any | None = None
    coach_prompt: Any | None = None
    counterpart_prompt: Any | None = None
    evaluator_prompt: Any | None = None
    scenario: Any | None = None
    counterpart_persona: Any | None = None
    app_session: Any | None = None

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
        corpus_index_id=simulation.corpus_index_id,
        coach_prompt_id=simulation.coach_prompt_id,
        counterpart_prompt_id=simulation.counterpart_prompt_id,
        evaluator_prompt_id=simulation.evaluator_prompt_id,
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


def _record_context(record: Any) -> dict[str, Any]:
    """
    Extract context information from a record.
    Args:
        record: The record from which to extract context.
    Returns:
        A dictionary containing the context information.
    """
    context = {"id": getattr(record, "id", None)}
    for field_name in ("name", "description"):
        value = getattr(record, field_name, None)
        if value is not None:
            context[field_name] = value
    return _json_safe(context)


async def _get_valid_built_corpus_index(
    corpus_id: int,
    corpus_index_id: int,
    session: AsyncSession,
) -> Any:
    """
    Validate and retrieve a built corpus index.
    Args:
        corpus_id: The ID of the corpus.
        corpus_index_id: The ID of the corpus index.
        session: The database session.
    Returns:
        The valid built corpus index.
    Raises:
        ValueError: If the corpus index is not found, does not belong to 
            the corpus,or is not built.
    """
    corpus_index = await corpus_indices_repo.get_corpus_index_by_id(corpus_index_id, session)
    if corpus_index is None:
        raise ValueError("Corpus index not found")
    if corpus_index.corpus_id != corpus_id:
        raise ValueError("Corpus index does not belong to simulation corpus")
    if corpus_index.status != "built":
        raise ValueError("Corpus index must be built before simulation use")
    return corpus_index


def _prompt_template(prompt: Any, prompt_role: str) -> str:
    """
    Extract the prompt template from a prompt object.
    Args:
        prompt: The prompt object containing messages.
        prompt_role: The role of the prompt (e.g., "coach", 
            "counterpart", "evaluator").
    Returns:
        The extracted prompt template as a string.
    Raises:
        ValueError: If the prompt template is empty or not found.
    """
    messages = getattr(prompt, "messages", None)
    if isinstance(messages, dict):
        for key in ("template", "prompt", "content", "system", prompt_role):
            value = messages.get(key)
            if isinstance(value, str) and value.strip():
                return value
        if len(messages) == 1:
            value = next(iter(messages.values()))
            if isinstance(value, str) and value.strip():
                return value

    raise ValueError(f"{prompt_role.capitalize()} prompt template is empty")


async def _get_prompt_template(
    prompt_id: int | None,
    prompt_role: str,
    session: AsyncSession,
) -> tuple[Any | None, str | None]:
    """
    Get a prompt and its template by ID.
    Args:
        prompt_id: The ID of the prompt to retrieve.
        prompt_role: The role of the prompt (e.g., "coach", "counterpart",
            "evaluator").
        session: The database session.
    Returns:
        A tuple containing the prompt object and its template.
    """
    if prompt_id is None:
        return None, None

    prompt = await prompts_repo.get_prompt_by_id(prompt_id, session)
    if prompt is None:
        raise ValueError(f"{prompt_role.capitalize()} prompt not found")

    return prompt, _prompt_template(prompt, prompt_role)


async def _get_simulation_prompt_templates(
    simulation: Simulation,
    session: AsyncSession,
) -> tuple[dict[str, Any | None], dict[str, str | None]]:
    """
    Get the prompt objects and their templates for a simulation.
    Args:
        simulation: The simulation object.
        session: The database session.
    Returns:
        A tuple containing two dictionaries:
        - The first dictionary maps prompt roles to their prompt objects.
        - The second dictionary maps prompt roles to their prompt templates.
    """
    coach_prompt, coach_template = await _get_prompt_template(
        simulation.coach_prompt_id,
        "coach",
        session,
    )
    counterpart_prompt, counterpart_template = await _get_prompt_template(
        simulation.counterpart_prompt_id,
        "counterpart",
        session,
    )
    evaluator_prompt, evaluator_template = await _get_prompt_template(
        simulation.evaluator_prompt_id,
        "evaluator",
        session,
    )
    return (
        {
            "coach_prompt": coach_prompt,
            "counterpart_prompt": counterpart_prompt,
            "evaluator_prompt": evaluator_prompt,
        },
        {
            "coach": coach_template,
            "counterpart": counterpart_template,
            "evaluator": evaluator_template,
        },
    )


def _graph_cache_key(
    corpus_index: Any,
    vector_store: Any,
    prompt_templates: dict[str, str | None],
) -> tuple[Any, ...]:
    """
    Generate a cache key for the negotiation graph based on the corpus index,
    vector store, and prompt templates.
    Args:
        corpus_index: The corpus index object.
        vector_store: The vector store object.
        prompt_templates: A dictionary mapping prompt roles to their templates.
    Returns:
        A tuple representing the cache key.
    """
    return (
        getattr(corpus_index, "id", None),
        getattr(corpus_index, "embedding_model", None),
        getattr(corpus_index, "embedding_dimensions", None),
        getattr(corpus_index, "vector_namespace", None),
        getattr(vector_store, "id", None),
        getattr(vector_store, "backend", None),
        getattr(vector_store, "collection_name", None),
        getattr(vector_store, "path", None),
        getattr(vector_store, "table_name", None),
        prompt_templates.get("coach"),
        prompt_templates.get("counterpart"),
        prompt_templates.get("evaluator"),
    )


async def _instantiate_vector_store_for_index(corpus_index: Any, vector_store: Any) -> Any:
    """
    Instantiate a vector store for a given corpus index and vector store 
    configuration.
    Args:
        corpus_index: The corpus index object.
        vector_store: The vector store object.
    Returns:
        The instantiated vector store.
    """
    embedding_model, _metadata = choose_embedding_model(corpus_index.embedding_model)

    if vector_store.backend == "chroma":
        return instantiate_chroma_vector_store(
            embedding_model=embedding_model,
            collection_name=vector_store.collection_name or "negotiation_corpus",
            persist_directory=vector_store.path or "./chroma_db",
        )

    if vector_store.backend == "faiss":
        return load_faiss_vector_store(
            embeddings=embedding_model,
            path=vector_store.path or "./faiss_db",
        )

    if vector_store.backend == "pgvector":
        if not vector_store.table_name:
            raise ValueError("PGVector stores require table_name")
        return await instantiate_pgvector_store(
            vector_table_name=vector_store.table_name,
            embedding_model=embedding_model,
            embedding_model_name=corpus_index.embedding_model,
        )

    raise ValueError(f"Unsupported vector store backend: {vector_store.backend}")


def _make_crag_graph(retriever: Any) -> Any:
    """
    Create a CRAG graph using the provided retriever.
    Args:
        retriever: The retriever object.
    Returns:
        The CRAG graph.
    """
    from app.airag.chains.crag.crag import CRAGState, make_crag

    return make_crag(retriever_obj=retriever, state_schema=CRAGState)


async def _get_negotiation_graph_for_simulation(
    simulation: Simulation,
    session: AsyncSession,
) -> Any:
    """
    Get the negotiation graph for a simulation.
    Args:
        simulation: The simulation object.
        session: The database session.
    Returns:
        The negotiation graph.
    """
    corpus_index = await _get_valid_built_corpus_index(
        simulation.corpus_id,
        simulation.corpus_index_id,
        session,
    )
    vector_store = await vector_stores_repo.get_vector_store_by_id(
        corpus_index.vector_store_id,
        session,
    )
    if vector_store is None:
        raise ValueError("Vector store not found")

    _prompt_records, prompt_templates = await _get_simulation_prompt_templates(
        simulation,
        session,
    )
    cache_key = _graph_cache_key(corpus_index, vector_store, prompt_templates)
    cached_graph = NEGOTIATION_GRAPH_CACHE.get(cache_key)
    if cached_graph is not None:
        return cached_graph

    vector_store_runtime = await _instantiate_vector_store_for_index(
        corpus_index,
        vector_store,
    )
    retriever = make_dense_retriever(
        vector_store_runtime,
        metadata_filter={"corpus_index_id": corpus_index.id},
    )
    crag_graph = _make_crag_graph(retriever)
    graph = make_negotiation_graph(
        crag_graph=crag_graph,
        coach_prompt_template=prompt_templates["coach"],
        counterpart_prompt_template=prompt_templates["counterpart"],
        evaluator_prompt_template=prompt_templates["evaluator"],
    )
    NEGOTIATION_GRAPH_CACHE[cache_key] = graph
    return graph


def _runtime_context_snapshot(runtime_context: SimulationRuntimeContext) -> dict[str, Any]:
    """
    Create a snapshot of the runtime context.
    Args:
        runtime_context: The runtime context to snapshot.
    Returns:
        A dictionary containing the snapshot of the runtime context.
    """
    snapshot: dict[str, Any] = {}
    if runtime_context.corpus is not None:
        snapshot["corpus_context"] = _record_context(runtime_context.corpus)
    if runtime_context.corpus_index is not None:
        snapshot["corpus_index_context"] = _record_context(runtime_context.corpus_index)
    if runtime_context.coach_prompt is not None:
        snapshot["coach_prompt_context"] = _record_context(runtime_context.coach_prompt)
    if runtime_context.counterpart_prompt is not None:
        snapshot["counterpart_prompt_context"] = _record_context(
            runtime_context.counterpart_prompt
        )
    if runtime_context.evaluator_prompt is not None:
        snapshot["evaluator_prompt_context"] = _record_context(runtime_context.evaluator_prompt)
    if runtime_context.scenario is not None:
        snapshot["scenario_context"] = _record_context(runtime_context.scenario)
    if runtime_context.counterpart_persona is not None:
        snapshot["counterpart_persona_context"] = _record_context(
            runtime_context.counterpart_persona
        )
    if runtime_context.app_session is not None:
        snapshot["app_session_id"] = getattr(runtime_context.app_session, "id", None)
    return _json_safe(snapshot)


def _counterpart_side(user_side: str | None) -> str:
    """
    Determine the counterpart side based on the user's side.
    Args:
        user_side: The side of the user ("side_a" or "side_b").
    Returns:
        The counterpart side ("side_a" or "side_b").
    """
    return "side_a" if user_side == "side_b" else "side_b"


def _counterpart_persona_side_profile(persona: Any) -> dict[str, Any]:
    """
    Create a profile for the counterpart persona's side.
    Args:
        persona: The counterpart persona.
    Returns:
        A dictionary containing the profile information.
    """
    profile = {
        "persona_id": getattr(persona, "id", None),
        "name": getattr(persona, "name", None),
    }
    description = getattr(persona, "description", None)
    if description is not None:
        profile["description"] = description
    return _json_safe({key: value for key, value in profile.items() if value is not None})


def _side_profiles_with_context_defaults(
    simulation: Simulation,
    start_data: SimulationStartRequest,
    runtime_context: SimulationRuntimeContext,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Determine the side profiles with context defaults.
    Args:
        simulation: The simulation object.
        start_data: The data provided to start the simulation.
        runtime_context: The runtime context of the simulation.
    Returns:
        A tuple containing the side A and side B profiles.
    """
    side_a = dict(_json_safe(start_data.side_a) or {})
    side_b = dict(_json_safe(start_data.side_b) or {})
    if runtime_context.counterpart_persona is None:
        return side_a, side_b

    counterpart_side = _counterpart_side(simulation.user_side or "side_a")
    if counterpart_side == "side_a" and not side_a:
        side_a = _counterpart_persona_side_profile(runtime_context.counterpart_persona)
    if counterpart_side == "side_b" and not side_b:
        side_b = _counterpart_persona_side_profile(runtime_context.counterpart_persona)
    return side_a, side_b


async def _load_simulation_runtime_context(
    simulation: Simulation,
    session: AsyncSession,
) -> SimulationRuntimeContext:
    """
    Load the runtime context for a simulation.
    Args:
        simulation: The simulation object.
        session: The database session.
    Returns:
        The runtime context of the simulation.
    """
    corpus = await corpus_repo.get_corpus_by_id(simulation.corpus_id, session)
    if corpus is None:
        raise ValueError("Corpus not found")

    corpus_index = await _get_valid_built_corpus_index(
        simulation.corpus_id,
        simulation.corpus_index_id,
        session,
    )

    scenario = None
    if simulation.scenario_id is not None:
        scenario = await scenarios_repo.get_scenario_by_id(simulation.scenario_id, session)
        if scenario is None:
            raise ValueError("Scenario not found")

    counterpart_persona = None
    if simulation.counter_part_side_persona_id is not None:
        counterpart_persona = await counterpart_personas_repo.get_counterpart_persona_by_id(
            simulation.counter_part_side_persona_id,
            session,
        )
        if counterpart_persona is None:
            raise ValueError("Counterpart persona not found")

    app_session = None
    if simulation.session_id is not None:
        app_session = await sessions_repo.get_session_by_id(simulation.session_id, session)
        if app_session is None:
            raise ValueError("Session not found")

    prompt_records, _prompt_templates = await _get_simulation_prompt_templates(
        simulation,
        session,
    )

    return SimulationRuntimeContext(
        corpus=corpus,
        corpus_index=corpus_index,
        coach_prompt=prompt_records["coach_prompt"],
        counterpart_prompt=prompt_records["counterpart_prompt"],
        evaluator_prompt=prompt_records["evaluator_prompt"],
        scenario=scenario,
        counterpart_persona=counterpart_persona,
        app_session=app_session,
    )


def _initial_graph_state(
    simulation: Simulation,
    start_data: SimulationStartRequest,
    current_user: User,
    runtime_context: SimulationRuntimeContext | None = None,
) -> dict[str, Any]:
    """
    Initialize the graph state for a simulation.
    Args:
        simulation: The simulation for which to initialize the state.
        start_data: The data provided to start the simulation.
        current_user: The user who is starting the simulation.
        runtime_context: The runtime context of the simulation, 
        which may include corpus, scenario, counterpart persona, and app 
        session information. If not provided, a default context will be used.
    Returns:
        A dictionary representing the initial graph state.
    """
    runtime_context = runtime_context or SimulationRuntimeContext()
    side_a, side_b = _side_profiles_with_context_defaults(
        simulation,
        start_data,
        runtime_context,
    )
    phase = "opening" if side_a and side_b else "setup"
    simulation_id = str(simulation.id)
    state: dict[str, Any] = {
        "simulation_id": simulation_id,
        "session_id": simulation_id,
        "user_id": str(current_user.id),
        "user_side": simulation.user_side or "side_a",
        "side_a": side_a,
        "side_b": side_b,
        "messages": [],
        "phase": phase,
        "active_side": simulation.user_side or "side_a",
        "offer_history": [],
        "turn_count": 0,
        "event_log": ["api:simulation_started"],
        "max_turn_count": start_data.max_turn_count,
    }
    state.update(_runtime_context_snapshot(runtime_context))

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
    simulation_id = str(simulation.id)
    state.setdefault("simulation_id", state.get("session_id", simulation_id))
    state.setdefault("session_id", state["simulation_id"])
    if simulation.session_id is not None:
        state.setdefault("app_session_id", simulation.session_id)
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
    await _get_valid_built_corpus_index(
        simulation_data.corpus_id,
        simulation_data.corpus_index_id,
        session,
    )
    await _get_prompt_template(simulation_data.coach_prompt_id, "coach", session)
    await _get_prompt_template(
        simulation_data.counterpart_prompt_id,
        "counterpart",
        session,
    )
    await _get_prompt_template(simulation_data.evaluator_prompt_id, "evaluator", session)
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
    corpus_index_id: int | None = None,
    coach_prompt_id: int | None = None,
    counterpart_prompt_id: int | None = None,
    evaluator_prompt_id: int | None = None,
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
        corpus_index_id: The ID of the corpus index to filter by.
        coach_prompt_id: The ID of the coach prompt to filter by.
        counterpart_prompt_id: The ID of the counterpart prompt to filter by.
        evaluator_prompt_id: The ID of the evaluator prompt to filter by.
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
        corpus_index_id=corpus_index_id,
        coach_prompt_id=coach_prompt_id,
        counterpart_prompt_id=counterpart_prompt_id,
        evaluator_prompt_id=evaluator_prompt_id,
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
    if simulation_data.corpus_index_id is not None:
        await _get_valid_built_corpus_index(
            simulation.corpus_id,
            simulation_data.corpus_index_id,
            session,
        )
    if simulation_data.coach_prompt_id is not None:
        await _get_prompt_template(simulation_data.coach_prompt_id, "coach", session)
    if simulation_data.counterpart_prompt_id is not None:
        await _get_prompt_template(
            simulation_data.counterpart_prompt_id,
            "counterpart",
            session,
        )
    if simulation_data.evaluator_prompt_id is not None:
        await _get_prompt_template(
            simulation_data.evaluator_prompt_id,
            "evaluator",
            session,
        )
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

    runtime_context = await _load_simulation_runtime_context(simulation, session)
    state = _initial_graph_state(simulation, start_data, current_user, runtime_context)
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

    graph = negotiation_graph or await _get_negotiation_graph_for_simulation(simulation, session)
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


async def review_simulation_srvc(
    simulation: Simulation,
    review_data: SimulationTeacherReviewRequest,
    session: AsyncSession,
    current_teacher: User,
) -> SimulationRead:
    """
    Store a teacher review for a simulation.
    Args:
        simulation: The simulation instance to review.
        review_data: The data for the teacher review, including feedback.
        session: The database session.
        current_teacher: The teacher submitting the review.
    Returns:
        A SimulationRead containing the updated simulation with the review.
     Raises:
        ValueError: If the current user is not a teacher or if the review 
        cannot be submitted due to the simulation's current status.
    """
    review_in = SimulationTeacherReview(
        teacher_id=current_teacher.id,
        teacher_feedback=review_data.teacher_feedback,
    )
    updated_simulation = await simulations_repo.review_simulation(
        simulation,
        review_in,
        session,
    )
    return _read_simulation(updated_simulation)
