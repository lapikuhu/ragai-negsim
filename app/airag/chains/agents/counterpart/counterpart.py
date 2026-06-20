from typing import Annotated, Any
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables.config import RunnableConfig
from langsmith import traceable

# local imports
from app.airag.chains.agents.helpers import json_dumps, format_messages
from app.airag.chains.agents.context_projections import project_counterpart_state
from app.airag.chains.negotiation.negotiation_model import (
	ParentNegotiationState,
)
from app.airag.prompts.neg_prompts.md_loader import COUNTERPART_PROMPT
from app.airag.chains.agents.counterpart.counterpart_model import(
	CounterpartGraphState,
)
from app.airag.chains.agents.counterpart.counterpart_helpers import (
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
from app.airag.observability.llm_usage import extend_runnable_config, invoke_with_config


def make_counterpart_graph(
	model: Any = None,
	prompt_template: str | None = None,
	state_schema: type[CounterpartGraphState] = CounterpartGraphState,
):
	"""
	Build and compile the counterpart graph.
	Args:
		model: The model to use for generating and repairing counterpart 
			responses.
		prompt_template: Optional custom prompt template for the 
			counterpart.
		state_schema: The schema class for the graph state, defaulting to 
			CounterpartGraphState.
	Returns:
		A compiled StateGraph instance representing the counterpart 
		response generation flow.
	"""
	counterpart_model = model or get_default_counterpart_model()

	counterpart_flow = StateGraph(state_schema)
	counterpart_flow.add_node("prepare_context", node_prepare_counterpart_context)
	counterpart_flow.add_node(
		"generate_counterpart_response",
		make_generate_counterpart_response_node(counterpart_model, prompt_template),
	)
	counterpart_flow.add_node(
		"repair_counterpart_response",
		make_repair_counterpart_response_node(counterpart_model, prompt_template),
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
	"""
	Wrap the counterpart graph as a parent negotiation graph node.
	Args:
		counterpart_graph: The compiled counterpart StateGraph to invoke.
	Returns:
		A function that can be used as a node in the parent negotiation graph,
		invoking the counterpart graph and returning the relevant updates to
		the parent graph state.
	"""
	@traceable
	def counterpart_node(
		state: ParentNegotiationState,
		config: RunnableConfig | None = None,
	) -> dict:
		"""
		Invoke the counterpart graph with the projected state and return 
		updates to the parent graph state.
		Args:
			state: The current parent graph state containing negotiation context.
		Returns:
			A dictionary with updates to the parent graph state based on the
			counterpart graph response, including the current offer, event log,
			and any messages from the counterpart.
		"""
		node_config = extend_runnable_config(
			config,
			tags=["agent:counterpart", "graph:counterpart"],
			metadata={"agent": "counterpart", "graph": "counterpart"},
			run_name="counterpart.graph",
		)
		result = invoke_with_config(
			counterpart_graph,
			project_counterpart_state(state),
			node_config,
		)
		response = result.get("counterpart_response", {})
		side = response.get("side", result.get("counterpart_side"))
		offer = response.get("offer", {})
		message = response.get("message", "")

		updates: dict[str, Any] = {
			"current_offer": offer,
			"event_log": result.get("event_log", []),
		}
		if message:
			updates["messages"] = [
				{
					"role": "assistant",
					"content": message,
					"side": side,
				}
			]
		if side == "side_a":
			updates["side_a_response"] = message
		elif side == "side_b":
			updates["side_b_response"] = message
		if offer:
			updates["offer_history"] = [offer]
		if result.get("evidence_ledger"):
			updates["evidence_ledger"] = result["evidence_ledger"]

		return updates

	return counterpart_node


@traceable
def invoke_counterpart_response(
	counterpart_graph: Any,
	state: ParentNegotiationState,
	config: RunnableConfig | None = None,
) -> dict[str, Any]:
	"""
	Invoke the counterpart graph and return only the validated response.
	Args:
		counterpart_graph: The compiled counterpart StateGraph to invoke.
		state: The current parent graph state containing negotiation context.
	Returns:
		A dictionary with the validated counterpart response.
	"""
	graph_config = extend_runnable_config(
		config,
		tags=["agent:counterpart", "graph:counterpart"],
		metadata={"agent": "counterpart", "graph": "counterpart"},
		run_name="counterpart.invoke_response",
	)
	result = invoke_with_config(counterpart_graph, state, graph_config)
	return result.get("counterpart_response", {})
