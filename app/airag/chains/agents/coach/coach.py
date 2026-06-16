from typing import Annotated, Any, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, START, END
from langsmith import traceable
from app.airag.chains.negotiation.negotiation_model import ParentNegotiationState, CoachAdvice
from app.airag.chains.agents.context_projections import project_coach_state
from app.airag.chains.agents.coach.coach_model import CoachGraphState
from app.airag.chains.agents.coach.coach_nodes import (
	decide_after_generate,
	decide_after_repair,
	node_prepare_coach_context,
	node_route_crag_queries,
	make_call_crag_node,
	make_generate_coach_advice_node,
	make_repair_coach_advice_node,
	node_fallback_coach_advice,
	node_finalize_coach,
)
from app.airag.chains.agents.coach.coach_helpers import get_default_coach_model


### -------------- END OF NODE AND ROUTER FUNCTIONS ---------------- ###

### ---------------------- GRAPH CONSTRUCTION ---------------------- ###
def make_coach_graph(
	crag_graph: Any = None,
	model: Any = None,
	prompt_template: str | None = None,
	state_schema: type[CoachGraphState] = CoachGraphState,
):
	"""Build and compile the coach graph."""
	coach_model = model or get_default_coach_model()

	coach_flow = StateGraph(state_schema)
	coach_flow.add_node("prepare_context", node_prepare_coach_context)
	coach_flow.add_node("route_crag_queries", node_route_crag_queries)
	coach_flow.add_node("call_crag", make_call_crag_node(crag_graph))
	coach_flow.add_node(
		"generate_coach_advice",
		make_generate_coach_advice_node(coach_model, prompt_template),
	)
	coach_flow.add_node(
		"repair_coach_advice",
		make_repair_coach_advice_node(coach_model, prompt_template),
	)
	coach_flow.add_node("fallback_coach_advice", node_fallback_coach_advice)
	coach_flow.add_node("finalize_coach", node_finalize_coach)

	coach_flow.add_edge(START, "prepare_context")
	coach_flow.add_edge("prepare_context", "route_crag_queries")
	coach_flow.add_edge("route_crag_queries", "call_crag")
	coach_flow.add_edge("call_crag", "generate_coach_advice")
	coach_flow.add_conditional_edges(
		"generate_coach_advice",
		decide_after_generate,
		{
			"finalize": "finalize_coach",
			"repair": "repair_coach_advice",
			"fallback": "fallback_coach_advice",
		},
	)
	coach_flow.add_conditional_edges(
		"repair_coach_advice",
		decide_after_repair,
		{
			"finalize": "finalize_coach",
			"fallback": "fallback_coach_advice",
		},
	)
	coach_flow.add_edge("fallback_coach_advice", "finalize_coach")
	coach_flow.add_edge("finalize_coach", END)

	return coach_flow.compile()


def make_coach_node(coach_graph: Any):
	"""Wrap the coach graph as a parent negotiation graph node."""
	@traceable
	def coach_node(state: ParentNegotiationState) -> dict:
		result = coach_graph.invoke(project_coach_state(state))
		updates = {"coach_advice": result.get("coach_advice", {})}
		if result.get("event_log"):
			updates["event_log"] = result["event_log"]
		return updates

	return coach_node


@traceable
def invoke_coach_advice(coach_graph: Any, state: ParentNegotiationState) -> CoachAdvice:
	"""Invoke the coach graph and return only the generated advice."""
	result = coach_graph.invoke(state)
	return result.get("coach_advice", {})

