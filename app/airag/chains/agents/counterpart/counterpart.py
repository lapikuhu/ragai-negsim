from typing import Annotated, Any, Literal

from langgraph.graph import StateGraph, START, END

# local imports
from app.airag.chains.agents.helpers import json_dumps, format_messages
from app.airag.chains.negotiation.negotiation_model import (
	CoachAdvice,
	Evaluation,
	Offer,
	ParentNegotiationState,
	RetrievalResult,
	Side,
	SideProfile,
)
from app.airag.prompts.neg_prompts.md_loader import COUNTERPART_PROMPT

from app.airag.chains.agents.counterpart.counterpart_model import(
	CounterpartAction,
	RiskLevel,
	CounterpartOfferModel,
	CounterpartPrivateNotesModel,
    CounterpartResponseModel,
	CounterpartGraphState,
)

from app.airag.chains.agents.counterpart.counterpart_helpers import (
	get_counterpart_side,
    get_side_profile,
	get_counterpart_profile,
    collect_missing_information,
	render_counterpart_prompt,
	get_retrieval_context,
    coerce_counterpart_response,
	fallback_counterpart_response,
    get_default_counterpart_model,
)

from app.airag.chains.agents.counterpart.counterpart_nodes import (
    node_prepare_counterpart_context,
    make_generate_counterpart_response_node,
    make_repair_counterpart_response_node,
    node_fallback_counterpart_response,
    node_finalize_counterpart,
    decide_after_generate,
    decide_after_repair,
)


def make_counterpart_graph(
	model: Any = None,
	state_schema: type[CounterpartGraphState] = CounterpartGraphState,
):
	"""Build and compile the counterpart graph."""
	counterpart_model = model or get_default_counterpart_model()

	counterpart_flow = StateGraph(state_schema)
	counterpart_flow.add_node("prepare_context", node_prepare_counterpart_context)
	counterpart_flow.add_node(
		"generate_counterpart_response",
		make_generate_counterpart_response_node(counterpart_model),
	)
	counterpart_flow.add_node(
		"repair_counterpart_response",
		make_repair_counterpart_response_node(counterpart_model),
	)
	counterpart_flow.add_node("fallback_counterpart_response", node_fallback_counterpart_response)
	counterpart_flow.add_node("finalize_counterpart", node_finalize_counterpart)

	counterpart_flow.add_edge(START, "prepare_context")
	counterpart_flow.add_edge("prepare_context", "generate_counterpart_response")
	counterpart_flow.add_conditional_edges(
		"generate_counterpart_response",
		decide_after_generate,
		{
			"finalize": "finalize_counterpart",
			"repair": "repair_counterpart_response",
			"fallback": "fallback_counterpart_response",
		},
	)
	counterpart_flow.add_conditional_edges(
		"repair_counterpart_response",
		decide_after_repair,
		{
			"finalize": "finalize_counterpart",
			"fallback": "fallback_counterpart_response",
		},
	)
	counterpart_flow.add_edge("fallback_counterpart_response", "finalize_counterpart")
	counterpart_flow.add_edge("finalize_counterpart", END)

	return counterpart_flow.compile()


def make_counterpart_node(counterpart_graph: Any):
	"""Wrap the counterpart graph as a parent negotiation graph node."""
	def counterpart_node(state: ParentNegotiationState) -> dict:
		original_event_count = len(state.get("event_log", []))
		result = counterpart_graph.invoke(state)
		response = result.get("counterpart_response", {})
		side = response.get("side", result.get("counterpart_side"))
		offer = response.get("offer", {})

		updates: dict[str, Any] = {
			"current_offer": offer,
			"event_log": result.get("event_log", [])[original_event_count:],
		}
		if side == "side_a":
			updates["side_a_response"] = response.get("message", "")
		elif side == "side_b":
			updates["side_b_response"] = response.get("message", "")
		if offer:
			updates["offer_history"] = [offer]

		return updates

	return counterpart_node


def invoke_counterpart_response(
	counterpart_graph: Any,
	state: ParentNegotiationState,
) -> dict[str, Any]:
	"""Invoke the counterpart graph and return only the validated response."""
	result = counterpart_graph.invoke(state)
	return result.get("counterpart_response", {})