import operator
from typing import Annotated, Any, Literal

from langchain_core.messages import BaseMessage
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langsmith import traceable
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing_extensions import TypedDict

from app.airag.chains.agents.coach.coach import make_coach_graph, make_coach_node
from app.airag.chains.agents.counterpart.counterpart import (
    make_counterpart_graph,
    make_counterpart_node,
)
from app.airag.chains.agents.evaluator.evaluator import (
    make_evaluator_graph,
    make_evaluator_node,
)
from app.airag.chains.agents.intent_classifier.intent_classifier import (
    make_intent_classifier_graph,
    make_intent_classifier_node,
)
from app.airag.chains.negotiation.negotiation_model import (
    CoachAdvice,
    Evaluation,
    EvaluationMode,
    FinalEvaluation,
    IntentClassification,
    NegotiationPhase,
    NextAction,
    Offer,
    ParentNegotiationState,
    RequestedAction,
    RetrievalResult,
    Side,
    SideProfile,
    TerminalReason,
)
from app.airag.observability.llm_usage import extend_runnable_config, invoke_with_config


class SideProfileRuntimeModel(BaseModel):
    """Runtime validation for side profile fields used by the orchestrator."""

    model_config = ConfigDict(extra="allow")

    side_id: str | None = None
    name: str | None = None
    role: str | None = None
    goal: str | None = None
    constraints: list[str] = Field(default_factory=list)
    batna: str | None = None
    reservation_value: float | None = None
    target_value: float | None = None
    value_preference: Literal["higher_is_better", "lower_is_better"] | None = None


class OfferRuntimeModel(BaseModel):
    """Runtime validation for offers in the parent graph."""

    model_config = ConfigDict(extra="allow")

    side: Side | None = None
    price: float | None = None
    terms: dict[str, Any] = Field(default_factory=dict)
    raw_text: str | None = None


class ParentNegotiationRuntimeModel(BaseModel):
    """Permissive parent-state validator with strict enum checks."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    simulation_id: str | None = None
    app_session_id: int | None = None
    session_id: str | None = None
    user_id: str | None = None
    counterpart_persona: dict[str, Any] = Field(default_factory=dict)
    scenario_public_context: dict[str, Any] = Field(default_factory=dict)
    side_a_private_context: dict[str, Any] = Field(default_factory=dict)
    side_b_private_context: dict[str, Any] = Field(default_factory=dict)
    user_side: Side | None = None
    side_a: SideProfileRuntimeModel | None = None
    side_b: SideProfileRuntimeModel | None = None
    messages: list[Any] = Field(default_factory=list)
    phase: NegotiationPhase | None = None
    active_side: Side | None = None
    current_offer: OfferRuntimeModel | None = None
    offer_history: list[OfferRuntimeModel] = Field(default_factory=list)
    coach_advice: dict[str, Any] = Field(default_factory=dict)
    side_a_response: str | None = None
    side_b_response: str | None = None
    evaluation: dict[str, Any] = Field(default_factory=dict)
    final_evaluation: dict[str, Any] = Field(default_factory=dict)
    retrieval_result: dict[str, Any] = Field(default_factory=dict)
    next_action: NextAction | None = None
    requested_action: RequestedAction | None = None
    intent_classification: dict[str, Any] = Field(default_factory=dict)
    evaluation_mode: EvaluationMode | None = None
    terminal_reason: TerminalReason | None = None
    turn_count: int = 0
    max_turn_count: int = 12
    should_pause: bool = False
    pause_reason: str | None = None
    evidence_ledger: dict[str, Any] = Field(default_factory=dict)
    event_log: list[str] = Field(default_factory=list)


class NegotiationGraphOutputModel(BaseModel):
    """Final parent-safe output validator."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    phase: NegotiationPhase | None = None
    turn_count: int = 0
    should_pause: bool = False
    pause_reason: str | None = None
    terminal_reason: TerminalReason | None = None
    event_log: list[str] = Field(default_factory=list)


class NegotiationGraphState(TypedDict, total=False):
    """State consumed and produced by the parent negotiation graph."""

    simulation_id: str
    app_session_id: int
    session_id: str
    user_id: str
    counterpart_persona: dict[str, Any]
    scenario_public_context: dict[str, Any]
    side_a_private_context: dict[str, Any]
    side_b_private_context: dict[str, Any]
    user_side: Side
    side_a: SideProfile
    side_b: SideProfile
    messages: Annotated[list[Any], add_messages]
    phase: NegotiationPhase
    active_side: Side
    current_offer: Offer
    offer_history: Annotated[list[Offer], operator.add]
    coach_advice: CoachAdvice
    side_a_response: str
    side_b_response: str
    evaluation: Evaluation
    final_evaluation: FinalEvaluation
    retrieval_result: RetrievalResult
    next_action: NextAction
    requested_action: RequestedAction
    intent_classification: IntentClassification
    evaluation_mode: EvaluationMode
    terminal_reason: TerminalReason
    turn_count: int
    evidence_ledger: dict[str, Any]
    event_log: Annotated[list[str], operator.add]
    should_pause: bool
    pause_reason: str
    orchestrator_validation_error: str
    max_turn_count: int


def get_latest_message_side(state: NegotiationGraphState) -> Side | None:
    """
    Infer side metadata from the latest message using common message shapes.
    Args:
		state: The current state of the negotiation graph, which includes 
        	a list of messages.
    Returns:
		The side associated with the latest message, or None if it cannot 
        	be inferred.
    """
    messages = state.get("messages", [])
    if not messages:
        return None

    latest_message = messages[-1]
    if isinstance(latest_message, dict):
        for key in ("side", "sender", "role", "name"):
            value = latest_message.get(key)
            if value in {"side_a", "side_b"}:
                return value

    if isinstance(latest_message, BaseMessage):
        if latest_message.name in {"side_a", "side_b"}:
            return latest_message.name
        for key in ("side", "sender", "role", "name"):
            value = latest_message.additional_kwargs.get(key)
            if value in {"side_a", "side_b"}:
                return value

    for attr_name in ("side", "sender", "role", "name"):
        value = getattr(latest_message, attr_name, None)
        if value in {"side_a", "side_b"}:
            return value

    return None


def normalize_phase(state: NegotiationGraphState) -> NegotiationPhase:
    """
    Normalize the negotiation phase.
    Args:
		state: The current state of the negotiation graph, which may include 
			various combinations of metadata fields.
    Returns:
		A normalized negotiation phase inferred from the state, 
        	defaulting to "setup" if it cannot be determined from 
            explicit phase or side metadata.
    """
    if state.get("phase"):
        return state["phase"]
    if state.get("side_a") and state.get("side_b"):
        return "opening"
    return "setup"


def turn_limit_reached(state: NegotiationGraphState) -> bool:
    """
    Determine whether the configured turn limit has been reached.
    Args:
        state: The current state of the negotiation graph, which includes 
            turn count and maximum turn count.
    Returns:
        True if the turn limit has been reached, False otherwise.
    """
    return state.get("turn_count", 0) >= state.get("max_turn_count", 12)


def validate_parent_state(state: NegotiationGraphState) -> str:
    """
    Validate the parent negotiation state without changing control flow.
    Args:
        state: The current state of the negotiation graph, which includes 
            various metadata fields.
    Returns:
        An error message if validation fails, or an empty string if 
        validation succeeds.
    """
    try:
        ParentNegotiationRuntimeModel.model_validate(dict(state))
    except ValidationError as exc:
        return str(exc)
    return ""


def route_after_prepare(state: NegotiationGraphState) -> str:
    """
    Choose the first deterministic branch after state preparation.
    Args:
        state: The current state of the negotiation graph, which includes 
            various metadata fields.
    Returns:
        The next route based on the current state.
    """
    if turn_limit_reached(state):
        return "final"
    requested_action = state.get("requested_action")
    if requested_action == "end":
        return "final"
    if requested_action == "continue":
        return "counterpart"
    return "classify"


def route_after_intent(state: NegotiationGraphState) -> str:
    """
    Route from classifier output into the normal or terminal path.
    Args:
        state: The current state of the negotiation graph, which includes 
            various metadata fields.
    Returns:
        The next route based on the classifier output.
    """
    classification = state.get("intent_classification", {})
    if (
        classification.get("intent") == "end"
        and classification.get("confidence") == "high"
    ):
        return "final"
    return "counterpart"


def node_prepare_orchestrator_context(state: NegotiationGraphState) -> dict:
    """
    Prepare one-shot routing state for the current invocation.
    Args:
        state: The current state of the negotiation graph, which includes 
            various metadata fields.
    Returns:
        A dictionary containing the prepared routing state.
    """
    phase = normalize_phase(state)
    latest_message_side = get_latest_message_side(state)
    requested_action = state.get("requested_action")
    validation_error = validate_parent_state({**state, "phase": phase})

    if turn_limit_reached(state):
        reason = "turn_limit_reached"
    elif requested_action:
        reason = f"requested_action={requested_action}"
    else:
        reason = "classify_end_intent"

    updates: dict[str, Any] = {
        "phase": phase,
        "max_turn_count": state.get("max_turn_count", 12),
        "turn_count": state.get("turn_count", 0),
        "active_side": state.get("active_side") or state.get("user_side"),
        "requested_action": requested_action,
        "should_pause": False,
        "pause_reason": "",
        "intent_classification": {},
        "terminal_reason": None,
        "evaluation_mode": state.get("evaluation_mode"),
        "orchestrator_validation_error": validation_error,
        "event_log": [
            f"orchestrator:prepared_context latest_message_side={latest_message_side} route_hint={reason}"
        ],
    }
    if not state.get("messages"):
        updates["messages"] = []
    if not state.get("offer_history"):
        updates["offer_history"] = []
    return updates


def node_prepare_final_evaluation(state: NegotiationGraphState) -> dict:
    """
    Set terminal evaluation mode and reason before final evaluation.
    Args:
        state: The current state of the negotiation graph, which includes 
            various metadata fields.
    Returns:
        A dictionary containing the updated state for final evaluation.
    """
    if turn_limit_reached(state):
        reason: TerminalReason = "turn_limit"
    elif state.get("requested_action") == "end":
        reason = "student_request"
    else:
        reason = "classified_intent"

    classification = state.get("intent_classification") or {}
    base_event = f"orchestrator:terminal reason={reason}"
    event = base_event
    if classification:
        event = (
            f"{base_event} "
            f"intent={classification.get('intent')} "
            f"confidence={classification.get('confidence')}"
        )

    return {
        "evaluation_mode": "final",
        "terminal_reason": reason,
        "should_pause": False,
        "pause_reason": "",
        "event_log": [base_event, event] if event != base_event else [base_event],
    }


def node_complete_counterpart_turn(state: NegotiationGraphState) -> dict:
    """
    Finalize deterministic state transitions after the counterpart acts.
    Args:
        state: The current state of the negotiation graph, which includes 
            various metadata fields.
    Returns:
        A dictionary containing the updated state after the counterpart's turn.
    """
    return {
        "turn_count": state.get("turn_count", 0) + 1,
        "active_side": state.get("user_side"),
        "evaluation_mode": "rolling",
        "event_log": ["orchestrator:counterpart_turn_completed"],
    }


def node_pause_for_user(state: NegotiationGraphState) -> dict:
    """
    Pause after a completed normal turn with visible counterpart output.
    Args:
        state: The current state of the negotiation graph, which includes 
            various metadata fields.
    Returns:
        A dictionary containing the updated state after pausing for the 
        user.
    """
    return {
        "should_pause": True,
        "pause_reason": "counterpart_response_ready",
        "event_log": ["orchestrator:paused reason=counterpart_response_ready"],
    }


def node_finalize_negotiation(state: NegotiationGraphState) -> dict:
    """
    Finalize the simulation after final evaluation completes.
    Args:
		state: The current state of the negotiation graph, which includes 
			various metadata fields.
    Returns:
        A dictionary containing the updated state after finalizing the 
        negotiation.
    """
    validation_error = ""
    try:
        NegotiationGraphOutputModel.model_validate(
            {
                **state,
                "phase": "ended",
                "should_pause": False,
                "pause_reason": "",
            }
        )
    except ValidationError as exc:
        validation_error = str(exc)

    return {
        "phase": "ended",
        "should_pause": False,
        "pause_reason": "",
        "orchestrator_validation_error": validation_error,
        "event_log": ["orchestrator:finalized"],
    }


def make_negotiation_graph(
    coach_graph: Any = None,
    counterpart_graph: Any = None,
    evaluator_graph: Any = None,
    intent_classifier_graph: Any = None,
    rag_graph: Any = None,
    retrieval_strategy: str = "crag",
    coach_model: Any = None,
    counterpart_model: Any = None,
    evaluator_model: Any = None,
    intent_classifier_model: Any = None,
    coach_prompt_template: str | None = None,
    counterpart_prompt_template: str | None = None,
    evaluator_prompt_template: str | None = None,
    state_schema: type[NegotiationGraphState] = NegotiationGraphState,
):
    """
    Build and compile the deterministic parent negotiation graph.
    Args:
		coach_graph: An optional pre-compiled graph for the coach node. If not
			provided, a default coach graph will be created using the specified
        counterpart_graph: An optional pre-compiled graph for the counterpart 
        	node. If not provided, a default counterpart graph will be created.
        evaluator_graph: An optional pre-compiled graph for the evaluator node.
			If not provided, a default evaluator graph will be created.
        intent_classifier_graph: An optional pre-compiled graph for the intent
			classifier node. If not provided, a default intent classifier 
            graph will be created.
        rag_graph: An optional RAG graph to use as a retrieval backend 
        	for the negotiation nodes.
        coach_model: An optional language model to use in the coach graph,
        	which should be compatible with the prompts used in the 
            coach graph.
		counterpart_model: An optional language model to use in the 
			counterpart graph, which should be compatible with the prompts 
			used in the counterpart graph.
        evaluator_model: An optional language model to use in the evaluator
			graph, which should be compatible with the prompts used in the 
			evaluator graph.
        intent_classifier_model: An optional language model to use in 
        	the intent classifier graph, which should support structured 
            output with IntentClassificationModel, and should be compatible 
            with the prompts used in the intent classifier graph.
		coach_prompt_template: An optional prompt template to use in the 
        	coach graph, which should be compatible with the coach model. If
            not provided, a default prompt template will be used.
        counterpart_prompt_template: An optional prompt template to use in the
			counterpart graph, which should be compatible with the counterpart
			model. If not provided, a default prompt template will be used.
		evaluator_prompt_template: An optional prompt template to use in the
			evaluator graph, which should be compatible with the evaluator 
            model. If not provided, a default prompt template will be used.
        state_schema: The Pydantic model class to use for validating the graph
			state, which should be compatible with NegotiationGraphState.
    Returns:
		A compiled StateGraph instance representing the parent negotiation 
        flow.
    """
    coach_graph = coach_graph or make_coach_graph(
        rag_graph=rag_graph,
        retrieval_strategy=retrieval_strategy,
        model=coach_model,
        prompt_template=coach_prompt_template,
    )
    counterpart_graph = counterpart_graph or make_counterpart_graph(
        model=counterpart_model,
        prompt_template=counterpart_prompt_template,
    )
    evaluator_graph = evaluator_graph or make_evaluator_graph(
        rag_graph=rag_graph,
        retrieval_strategy=retrieval_strategy,
        model=evaluator_model,
        prompt_template=evaluator_prompt_template,
    )
    intent_classifier_graph = intent_classifier_graph or make_intent_classifier_graph(
        model=intent_classifier_model
    )

    negotiation_flow = StateGraph(state_schema)
    negotiation_flow.add_node("prepare_context", node_prepare_orchestrator_context)
    negotiation_flow.add_node(
        "classify_intent",
        make_intent_classifier_node(intent_classifier_graph),
    )
    negotiation_flow.add_node(
        "call_counterpart",
        make_counterpart_node(counterpart_graph),
    )
    negotiation_flow.add_node(
        "complete_counterpart_turn",
        node_complete_counterpart_turn,
    )
    negotiation_flow.add_node(
        "rolling_evaluator",
        make_evaluator_node(evaluator_graph),
    )
    negotiation_flow.add_node("coach", make_coach_node(coach_graph))
    negotiation_flow.add_node(
        "prepare_final_evaluation",
        node_prepare_final_evaluation,
    )
    negotiation_flow.add_node(
        "final_evaluator",
        make_evaluator_node(evaluator_graph),
    )
    negotiation_flow.add_node("pause_for_user", node_pause_for_user)
    negotiation_flow.add_node("finalize", node_finalize_negotiation)

    negotiation_flow.add_edge(START, "prepare_context")
    negotiation_flow.add_conditional_edges(
        "prepare_context",
        route_after_prepare,
        {
            "classify": "classify_intent",
            "counterpart": "call_counterpart",
            "final": "prepare_final_evaluation",
        },
    )
    negotiation_flow.add_conditional_edges(
        "classify_intent",
        route_after_intent,
        {
            "counterpart": "call_counterpart",
            "final": "prepare_final_evaluation",
        },
    )
    negotiation_flow.add_edge("call_counterpart", "complete_counterpart_turn")
    negotiation_flow.add_edge("complete_counterpart_turn", "rolling_evaluator")
    negotiation_flow.add_edge("rolling_evaluator", "coach")
    negotiation_flow.add_edge("coach", "pause_for_user")
    negotiation_flow.add_edge("prepare_final_evaluation", "final_evaluator")
    negotiation_flow.add_edge("final_evaluator", "finalize")
    negotiation_flow.add_edge("pause_for_user", END)
    negotiation_flow.add_edge("finalize", END)

    return negotiation_flow.compile()


@traceable
def invoke_negotiation_turn(
    negotiation_graph: Any,
    state: ParentNegotiationState,
    config: RunnableConfig | None = None,
) -> ParentNegotiationState:
    """
    Invoke one orchestrated negotiation turn and return updated parent state.
    Args:
		negotiation_graph: The compiled parent negotiation graph to invoke.
		state: The current parent negotiation state to pass into the graph.
        config: Optional runnable configuration to customize the invocation.
    Returns:
		The updated parent negotiation state after invoking the graph.
    """
    graph_config = extend_runnable_config(
        config,
        tags=["graph:negotiation"],
        metadata={"graph": "negotiation"},
        run_name="negotiation.invoke_turn",
    )
    return invoke_with_config(negotiation_graph, state, graph_config)
