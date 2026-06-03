import operator
from typing import Annotated, Any, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing_extensions import NotRequired, TypedDict

# local imports
from app.airag.chains.agents.coach.coach import make_coach_graph, make_coach_node
from app.airag.chains.agents.counterpart.counterpart import (
	make_counterpart_graph,
	make_counterpart_node,
)
from app.airag.chains.agents.evaluator.evaluator import (
	make_evaluator_graph,
	make_evaluator_node,
)
from app.airag.chains.negotiation.negotiation_model import (
	CoachAdvice,
	Evaluation,
	NegotiationPhase,
	NextAction,
	Offer,
	ParentNegotiationState,
	RetrievalResult,
	Side,
	SideProfile,
)


RouteTarget = Literal["counterpart", "coach", "evaluator", "pause", "finalize"]


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

	session_id: str | None = None
	user_id: str | None = None
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
	retrieval_result: dict[str, Any] = Field(default_factory=dict)
	next_action: NextAction | None = None
	turn_count: int = 0
	event_log: list[str] = Field(default_factory=list)


class RouteDecisionModel(BaseModel):
	"""Validated route decision used by orchestrator routers."""

	next_action: NextAction
	phase: NegotiationPhase
	active_side: Side | None = None
	should_pause: bool = False
	route: RouteTarget
	reason: str


class NegotiationGraphOutputModel(BaseModel):
	"""Final parent-safe output validator."""

	model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

	phase: NegotiationPhase | None = None
	next_action: NextAction | None = None
	turn_count: int = 0
	should_pause: bool = False
	pause_reason: str | None = None
	event_log: list[str] = Field(default_factory=list)


class NegotiationGraphState(TypedDict, total=False):
	"""State consumed and produced by the parent negotiation graph."""

	session_id: str
	user_id: str
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
	retrieval_result: RetrievalResult
	next_action: NextAction
	turn_count: int
	event_log: Annotated[list[str], operator.add]

	route_decision: dict[str, Any]
	should_pause: bool
	pause_reason: str
	orchestrator_validation_error: str
	orchestrator_step_count: int
	max_turn_count: int
	latest_message_side: Side | None
	has_fresh_user_message: bool
	post_counterpart_evaluated: bool


def get_counterpart_side(state: NegotiationGraphState) -> Side:
	"""Infer counterpart side as opposite the user-controlled side."""
	return "side_a" if state.get("user_side") == "side_b" else "side_b"


def get_latest_message_side(state: NegotiationGraphState) -> Side | None:
	"""Infer side metadata from the latest message using common message shapes."""
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


def has_latest_user_side_message(state: NegotiationGraphState) -> bool:
	"""
	Helper function to check if the latest message is from the 
	user-controlled side, which can inform routing decisions.
	"""
	return get_latest_message_side(state) == state.get("user_side")

# CHECK
def normalize_phase(state: NegotiationGraphState) -> NegotiationPhase:
	"""
	Helper function to normalize the negotiation phase.
	"""
	if state.get("phase"):
		return state["phase"]
	if state.get("side_a") and state.get("side_b"):
		return "opening"
	return "setup"


def max_turn_reached(state: NegotiationGraphState) -> bool:
	"""
	Helper function to determine if the maximum turn count has been reached, 
	which can trigger negotiation finalization to prevent infinite loops.
	"""
	max_turn_count = state.get("max_turn_count", 12)
	return state.get("turn_count", 0) >= max_turn_count or state.get(
		"orchestrator_step_count", 0
	) >= max_turn_count


def validate_parent_state(state: NegotiationGraphState) -> str:
	"""
	Helper function to validate the parent negotiation state.
	"""
	try:
		ParentNegotiationRuntimeModel.model_validate(dict(state))
	except ValidationError as exc:
		return str(exc)
	return ""


def validate_route_decision(decision: dict[str, Any]) -> tuple[dict[str, Any], str]:
	"""
	Helper function to validate the route decision.
	"""
	try:
		validated = RouteDecisionModel.model_validate(decision)
	except ValidationError as exc:
		return {
			"next_action": "ask_user",
			"phase": decision.get("phase", "setup"),
			"active_side": decision.get("active_side"),
			"should_pause": True,
			"route": "pause",
			"reason": "route decision validation failed",
		}, str(exc)
	return validated.model_dump(), ""

# CHECK: logic, very complex
def make_route_decision(state: NegotiationGraphState) -> tuple[dict[str, Any], str]:
	"""
	Helper function to make a route decision based on the current 
	negotiation state.
	"""
	phase = normalize_phase(state)
	next_action = state.get("next_action", "ask_user")
	active_side = state.get("active_side")
	should_pause = False
	route: RouteTarget = "pause"
	reason = "pause for user"

	if max_turn_reached(state):
		next_action = "end"
		should_pause = False
		route = "finalize"
		reason = "max turn count reached"
	elif next_action == "end" or phase == "ended":
		route = "finalize"
		reason = "evaluator requested end"
	elif next_action == "ask_user":
		should_pause = True # Pause for user input
		route = "pause"
		reason = "user input requested"
	elif state.get("has_fresh_user_message") and next_action in {
		"call_side_a",
		"call_side_b",
		"call_evaluator",
	}:
		target_side = next_action.replace("call_", "") if next_action.startswith("call_side") else get_counterpart_side(state)
		if target_side != state.get("user_side"):
			route = "counterpart"
			reason = "latest message is from user side, counterpart can respond"
		else:
			should_pause = True
			route = "pause"
			reason = "requested side is user side"
	elif next_action in {"call_side_a", "call_side_b"}:
		target_side = next_action.replace("call_", "")
		if target_side != state.get("user_side"):
			route = "counterpart"
			reason = f"evaluator requested {target_side}"
		else:
			should_pause = True # Pause for user input
			route = "pause"
			reason = "evaluator requested the user-controlled side"
	elif next_action == "call_coach":
		route = "coach"
		reason = "evaluator requested coach"
	elif next_action in {"call_evaluator", "call_retriever"}:
		route = "evaluator"
		reason = "evaluator requested another grounded evaluation"

	return validate_route_decision(
		{
			"next_action": next_action,
			"phase": phase,
			"active_side": active_side,
			"should_pause": should_pause,
			"route": route,
			"reason": reason,
		}
	)


def node_prepare_orchestrator_context(state: NegotiationGraphState) -> dict:
	"""
	Helper function to prepare the orchestrator context based on the current
	negotiation state.
	"""
	phase = normalize_phase(state)
	latest_message_side = get_latest_message_side(state)
	validation_error = validate_parent_state({**state, "phase": phase})
	updates: dict[str, Any] = {
		"phase": phase,
		"turn_count": state.get("turn_count", 0),
		"max_turn_count": state.get("max_turn_count", 12),
		"orchestrator_step_count": state.get("orchestrator_step_count", 0) + 1,
		"latest_message_side": latest_message_side,
		"has_fresh_user_message": latest_message_side == state.get("user_side"),
		"orchestrator_validation_error": validation_error,
		"event_log": [
			f"orchestrator:prepared_context latest_message_side={latest_message_side}"
		],
	}
	if not state.get("messages"):
		updates["messages"] = []
	if not state.get("offer_history"):
		updates["offer_history"] = []
	if not state.get("active_side") and state.get("user_side"):
		updates["active_side"] = state["user_side"]
	if not state.get("next_action"):
		updates["next_action"] = "call_coach"
	return updates


def node_validate_observation_outputs(state: NegotiationGraphState) -> dict:
	"""
	Helper function to validate the observation outputs based on the current
	negotiation state.
	"""
	validation_error = validate_parent_state(state)
	decision, decision_error = make_route_decision(state)
	if validation_error or decision_error:
		decision = {
			"next_action": "ask_user",
			"phase": normalize_phase(state),
			"active_side": state.get("active_side"),
			"should_pause": True,
			"route": "pause",
			"reason": "orchestrator validation failed",
		}

	return {
		"route_decision": decision,
		"next_action": decision["next_action"],
		"should_pause": decision["should_pause"],
		"pause_reason": decision["reason"] if decision["should_pause"] else "",
		"orchestrator_validation_error": validation_error or decision_error,
		"event_log": [f"orchestrator:routed route={decision['route']} reason={decision['reason']}"],
	}


def route_after_validation(state: NegotiationGraphState) -> str:
	"""
	Get the route target after validation from the state. This is used by the
	orchestrator to determine the next node to execute based on the route 
	decision.
	"""
	return state.get("route_decision", {}).get("route", "pause")


def node_set_user_active_after_counterpart(state: NegotiationGraphState) -> dict:
	"""
	Helper function to set the user as the active side after the counterpart's 
	turn.
	"""
	return {
		"active_side": state.get("user_side"),
		"turn_count": state.get("turn_count", 0) + 1,
		"post_counterpart_evaluated": False,
		"event_log": ["orchestrator:counterpart_completed_user_active"],
	}


def node_prepare_post_counterpart_evaluation(state: NegotiationGraphState) -> dict:
	"""
	Helper function to prepare the state for post-counterpart evaluation.
	"""
	return {
		"post_counterpart_evaluated": True,
		"event_log": ["orchestrator:post_counterpart_evaluation"],
	}

# VERY IMPORTANT
def node_pause_for_user(state: NegotiationGraphState) -> dict:
	"""
	Pauses the negotiation for user input, setting the appropriate pause 
	reason based on the current state. This node is used when the 
	orchestrator determines that it needs to wait for the user to take 
	an action before proceeding.
	"""
	if state.get("next_action") == "call_coach":
		reason = "coach_advice_ready"
	elif state.get("post_counterpart_evaluated"):
		reason = "counterpart_response_ready"
	else:
		reason = state.get("pause_reason") or state.get("route_decision", {}).get(
			"reason", "user action needed"
		)
	return {
		"next_action": "ask_user",
		"should_pause": True,
		"pause_reason": reason,
		"event_log": [f"orchestrator:paused_for_user reason={reason}"],
	}


def node_finalize_negotiation(state: NegotiationGraphState) -> dict:
	"""
	Finalizes the negotiation, performing any necessary validation and setting
	the final phase of the negotiation. This node is used when the orchestrator 
	determines that the negotiation should end.
	"""
	phase = "ended" if state.get("next_action") == "end" else normalize_phase(state)
	validation_error = ""
	try:
		NegotiationGraphOutputModel.model_validate({**state, "phase": phase})
	except ValidationError as exc:
		validation_error = str(exc)

	return {
		"phase": phase,
		"should_pause": False,
		"orchestrator_validation_error": validation_error,
		"event_log": ["orchestrator:completed"],
	}


def route_after_post_counterpart_evaluation(state: NegotiationGraphState) -> str:
	"""
	Route the next node after post-counterpart evaluation based on the 
	current state.
	"""
	if state.get("next_action") == "end" or max_turn_reached(state):
		return "finalize"
	if state.get("next_action") == "call_coach":
		return "coach"
	return "pause"


def route_after_single_evaluator(state: NegotiationGraphState) -> str:
	"""
	Route the next node after a single evaluator call based on the current 
	state.
	"""
	if state.get("next_action") == "end" or max_turn_reached(state):
		return "finalize"
	return "pause"

# Assembly function to build the negotiation graph
def make_negotiation_graph(
	coach_graph: Any = None,
	counterpart_graph: Any = None,
	evaluator_graph: Any = None,
	crag_graph: Any = None,
	coach_model: Any = None,
	counterpart_model: Any = None,
	evaluator_model: Any = None,
	state_schema: type[NegotiationGraphState] = NegotiationGraphState,
):
	"""Build and compile the parent negotiation orchestrator graph."""
	coach_graph = coach_graph or make_coach_graph(
		crag_graph=crag_graph,
		model=coach_model,
	)
	counterpart_graph = counterpart_graph or make_counterpart_graph(model=counterpart_model)
	evaluator_graph = evaluator_graph or make_evaluator_graph(
		crag_graph=crag_graph,
		model=evaluator_model,
	)

	negotiation_flow = StateGraph(state_schema)
	negotiation_flow.add_node("prepare_context", node_prepare_orchestrator_context)
	negotiation_flow.add_node("coach_observe", make_coach_node(coach_graph))
	negotiation_flow.add_node("evaluator_observe", make_evaluator_node(evaluator_graph))
	negotiation_flow.add_node("validate_observation", node_validate_observation_outputs)
	negotiation_flow.add_node("call_counterpart", make_counterpart_node(counterpart_graph))
	negotiation_flow.add_node("set_user_active", node_set_user_active_after_counterpart)
	negotiation_flow.add_node("post_counterpart_marker", node_prepare_post_counterpart_evaluation)
	negotiation_flow.add_node("post_counterpart_evaluator", make_evaluator_node(evaluator_graph))
	negotiation_flow.add_node("call_coach", make_coach_node(coach_graph))
	negotiation_flow.add_node("call_evaluator", make_evaluator_node(evaluator_graph))
	negotiation_flow.add_node("pause_for_user", node_pause_for_user)
	negotiation_flow.add_node("finalize", node_finalize_negotiation)

	negotiation_flow.add_edge(START, "prepare_context")
	negotiation_flow.add_edge("prepare_context", "coach_observe")
	negotiation_flow.add_edge("prepare_context", "evaluator_observe")
	negotiation_flow.add_edge("coach_observe", "validate_observation")
	negotiation_flow.add_edge("evaluator_observe", "validate_observation")
	negotiation_flow.add_conditional_edges(
		"validate_observation",
		route_after_validation,
		{
			"counterpart": "call_counterpart",
			"coach": "call_coach",
			"evaluator": "call_evaluator",
			"pause": "pause_for_user",
			"finalize": "finalize",
		},
	)
	negotiation_flow.add_edge("call_counterpart", "set_user_active")
	negotiation_flow.add_edge("set_user_active", "post_counterpart_marker")
	negotiation_flow.add_edge("post_counterpart_marker", "post_counterpart_evaluator")
	negotiation_flow.add_conditional_edges(
		"post_counterpart_evaluator",
		route_after_post_counterpart_evaluation,
		{
			"coach": "call_coach",
			"pause": "pause_for_user",
			"finalize": "finalize",
		},
	)
	negotiation_flow.add_edge("call_coach", "pause_for_user")
	negotiation_flow.add_conditional_edges(
		"call_evaluator",
		route_after_single_evaluator,
		{
			"pause": "pause_for_user",
			"finalize": "finalize",
		},
	)
	negotiation_flow.add_edge("pause_for_user", END)
	negotiation_flow.add_edge("finalize", END)

	return negotiation_flow.compile()


def invoke_negotiation_turn(
	negotiation_graph: Any,
	state: ParentNegotiationState,
) -> ParentNegotiationState:
	"""Invoke one orchestrated negotiation turn and return updated parent state."""
	return negotiation_graph.invoke(state)
