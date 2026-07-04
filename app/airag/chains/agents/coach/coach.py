from typing import Annotated, Any, Literal
from langchain_core.messages import BaseMessage
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langsmith import traceable
from app.airag.chains.negotiation.negotiation_model import ParentNegotiationState, CoachAdvice
from app.airag.chains.agents.context_projections import project_coach_state
from app.airag.chains.agents.coach.coach_model import CoachGraphState
from app.airag.chains.agents.coach.coach_nodes import (
	decide_after_generate,
	decide_after_repair,
	node_prepare_coach_context,
	node_route_rag_queries,
	make_call_rag_node,
	make_generate_coach_advice_node,
	make_repair_coach_advice_node,
	node_fallback_coach_advice,
	node_finalize_coach,
)
from app.airag.chains.agents.coach.coach_helpers import get_default_coach_model
from app.airag.observability.llm_usage import extend_runnable_config, invoke_with_config


### -------------- END OF NODE AND ROUTER FUNCTIONS ---------------- ###

### ---------------------- GRAPH CONSTRUCTION ---------------------- ###
def make_coach_graph(
	rag_graph: Any = None,
	retrieval_strategy: str = "crag",
	model: Any = None,
	prompt_template: str | None = None,
	state_schema: type[CoachGraphState] = CoachGraphState,
):
	"""
	Build and compile the coach graph.
	Args:
		rag_graph: Optional RAG graph to use for retrieval.
		retrieval_strategy: Strategy for retrieving information from RAG.
		model: Optional model to use for the coach.
		prompt_template: Optional prompt template for the coach.
		state_schema: Schema for the coach graph state.
	Returns:
		The compiled coach graph.
	"""
	coach_model = model or get_default_coach_model()

	coach_flow = StateGraph(state_schema)
	coach_flow.add_node("prepare_context", node_prepare_coach_context)
	coach_flow.add_node("route_rag_queries", node_route_rag_queries)
	coach_flow.add_node(
		"call_rag",
		make_call_rag_node(rag_graph, retrieval_strategy=retrieval_strategy),
	)
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
	coach_flow.add_edge("prepare_context", "route_rag_queries")
	coach_flow.add_edge("route_rag_queries", "call_rag")
	coach_flow.add_edge("call_rag", "generate_coach_advice")
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
	"""
	Wrap the coach graph as a parent negotiation graph node.
	"""
	@traceable
	def coach_node(
		state: ParentNegotiationState,
		config: RunnableConfig | None = None,
	) -> dict:
		node_config = extend_runnable_config(
			config,
			tags=["agent:coach", "graph:coach"],
			metadata={"agent": "coach", "graph": "coach"},
			run_name="coach.graph",
		)
		result = invoke_with_config(coach_graph, project_coach_state(state), node_config)
		updates = {"coach_advice": result.get("coach_advice", {})}
		if result.get("event_log"):
			updates["event_log"] = result["event_log"]
		if result.get("evidence_ledger"):
			updates["evidence_ledger"] = result["evidence_ledger"]
		return updates

	return coach_node


@traceable
def invoke_coach_advice(
	coach_graph: Any,
	state: ParentNegotiationState,
	config: RunnableConfig | None = None,
) -> CoachAdvice:
	"""
	Invoke the coach graph and return only the generated advice.
	Args:
		coach_graph: The compiled coach graph to invoke.
		state: The current negotiation state to pass to the coach graph.
		config: Optional RunnableConfig for execution settings.
	Returns:
		A CoachAdvice object containing the generated advice and related 
		information.
	"""
	graph_config = extend_runnable_config(
		config,
		tags=["agent:coach", "graph:coach"],
		metadata={"agent": "coach", "graph": "coach"},
		run_name="coach.invoke_advice",
	)
	result = invoke_with_config(coach_graph, state, graph_config)
	return result.get("coach_advice", {})
