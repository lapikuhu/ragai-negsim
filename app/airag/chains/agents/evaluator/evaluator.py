from typing import Any
from langgraph.graph import StateGraph, START, END

# local imports
from app.airag.chains.agents.evaluator.evaluator_helpers import (
    get_default_evaluator_model
)
from app.airag.chains.negotiation.negotiation_model import (
	Evaluation,
	ParentNegotiationState,
)
from app.airag.prompts.neg_prompts.md_loader import EVALUATOR_PROMPT

from app.airag.chains.agents.evaluator.evaluator_nodes import (
    node_prepare_evaluator_context,
    node_build_evaluator_crag_query,
    make_call_crag_node,
    make_generate_evaluator_response_node,
    make_repair_evaluator_response_node,
    node_fallback_evaluator_response,
    node_finalize_evaluator,
    decide_after_generate,
    decide_after_repair,
)
from app.airag.chains.agents.evaluator.evaluator_model import (
    EvaluatorGraphState
)

def make_evaluator_graph(
	crag_graph: Any = None,
	model: Any = None,
	prompt_template: str | None = None,
	state_schema: type[EvaluatorGraphState] = EvaluatorGraphState,
):
	"""Build and compile the evaluator graph."""
	evaluator_model = model or get_default_evaluator_model()

	evaluator_flow = StateGraph(state_schema)
	evaluator_flow.add_node("prepare_context", node_prepare_evaluator_context)
	evaluator_flow.add_node("build_crag_query", node_build_evaluator_crag_query)
	evaluator_flow.add_node("call_crag", make_call_crag_node(crag_graph))
	evaluator_flow.add_node(
		"generate_evaluator_response",
		make_generate_evaluator_response_node(evaluator_model, prompt_template),
	)
	evaluator_flow.add_node(
		"repair_evaluator_response",
		make_repair_evaluator_response_node(evaluator_model, prompt_template),
	)
	evaluator_flow.add_node("fallback_evaluator_response", node_fallback_evaluator_response)
	evaluator_flow.add_node("finalize_evaluator", node_finalize_evaluator)

	evaluator_flow.add_edge(START, "prepare_context")
	evaluator_flow.add_edge("prepare_context", "build_crag_query")
	evaluator_flow.add_edge("build_crag_query", "call_crag")
	evaluator_flow.add_edge("call_crag", "generate_evaluator_response")
	evaluator_flow.add_conditional_edges(
		"generate_evaluator_response",
		decide_after_generate,
		{
			"finalize": "finalize_evaluator",
			"repair": "repair_evaluator_response",
			"fallback": "fallback_evaluator_response",
		},
	)
	evaluator_flow.add_conditional_edges(
		"repair_evaluator_response",
		decide_after_repair,
		{
			"finalize": "finalize_evaluator",
			"fallback": "fallback_evaluator_response",
		},
	)
	evaluator_flow.add_edge("fallback_evaluator_response", "finalize_evaluator")
	evaluator_flow.add_edge("finalize_evaluator", END)

	return evaluator_flow.compile()


def make_evaluator_node(evaluator_graph: Any):
	"""Wrap the evaluator graph as a parent negotiation graph node."""
	def evaluator_node(state: ParentNegotiationState) -> dict:
		original_event_count = len(state.get("event_log", []))
		result = evaluator_graph.invoke(state)
		return {
			"evaluation": result.get("evaluation", {}),
			"next_action": result.get("next_action", "ask_user"),
			"event_log": result.get("event_log", [])[original_event_count:],
		}

	return evaluator_node


def invoke_evaluator_response(
	evaluator_graph: Any,
	state: ParentNegotiationState,
) -> dict[str, Any]:
	"""Invoke the evaluator graph and return the full validated response."""
	result = evaluator_graph.invoke(state)
	return result.get("evaluator_response", {})


def invoke_compact_evaluation(
	evaluator_graph: Any,
	state: ParentNegotiationState,
) -> Evaluation:
	"""Invoke the evaluator graph and return only compact Evaluation."""
	result = evaluator_graph.invoke(state)
	return result.get("evaluation", {})
