from typing import Any
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langsmith import traceable

# local imports
from app.airag.chains.agents.evaluator.evaluator_helpers import (
    get_default_evaluator_model
)
from app.airag.chains.agents.context_projections import project_evaluator_state
from app.airag.chains.negotiation.negotiation_model import (
	Evaluation,
	ParentNegotiationState,
)
from app.airag.prompts.neg_prompts.md_loader import EVALUATOR_PROMPT

from app.airag.chains.agents.evaluator.evaluator_nodes import (
    node_prepare_evaluator_context,
    node_build_evaluator_rag_query,
    make_call_rag_node,
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
from app.airag.observability.llm_usage import extend_runnable_config, invoke_with_config

def make_evaluator_graph(
	rag_graph: Any = None,
	retrieval_strategy: str = "crag",
	model: Any = None,
	prompt_template: str | None = None,
	state_schema: type[EvaluatorGraphState] = EvaluatorGraphState,
):
	"""
	Build and compile the evaluator graph.
	Args:
		rag_graph: The RAG graph to use for context retrieval.
		retrieval_strategy: The strategy to use for retrieving information 
			from RAG.
		model: The LLM model to use for generating evaluator responses.
		prompt_template: The template to use for rendering the evaluator 
			prompt.
		state_schema: The schema for the evaluator graph state.
	Returns:
		The compiled evaluator StateGraph.
	"""
	evaluator_model = model or get_default_evaluator_model()

	evaluator_flow = StateGraph(state_schema)
	evaluator_flow.add_node("prepare_context", node_prepare_evaluator_context)
	evaluator_flow.add_node("build_rag_query", node_build_evaluator_rag_query)
	evaluator_flow.add_node(
		"call_rag",
		make_call_rag_node(rag_graph, retrieval_strategy=retrieval_strategy),
	)
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
	evaluator_flow.add_edge("prepare_context", "build_rag_query")
	evaluator_flow.add_edge("build_rag_query", "call_rag")
	evaluator_flow.add_edge("call_rag", "generate_evaluator_response")
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
	"""
	Wrap the evaluator graph as a parent negotiation graph node.
	Args:
		evaluator_graph: The compiled evaluator StateGraph to wrap.
	Returns:
		A function that can be used as a node in the parent negotiation graph.
	"""
	@traceable
	def evaluator_node(
		state: ParentNegotiationState,
		config: RunnableConfig | None = None,
	) -> dict:
		node_config = extend_runnable_config(
			config,
			tags=["agent:evaluator", "graph:evaluator"],
			metadata={"agent": "evaluator", "graph": "evaluator"},
			run_name="evaluator.graph",
		)
		result = invoke_with_config(
			evaluator_graph,
			project_evaluator_state(state),
			node_config,
		)
		updates = {
			"event_log": result.get("event_log", []),
		}
		if state.get("evaluation_mode") == "final":
			updates["final_evaluation"] = result.get("final_evaluation", {})
		else:
			updates["evaluation"] = result.get("evaluation", {})
		if result.get("evidence_ledger"):
			updates["evidence_ledger"] = result["evidence_ledger"]
		return updates

	return evaluator_node


@traceable
def invoke_evaluator_response(
	evaluator_graph: Any,
	state: ParentNegotiationState,
	config: RunnableConfig | None = None,
) -> dict[str, Any]:
	"""
	Invoke the evaluator graph and return the full validated response.
	Args:
		evaluator_graph: The compiled evaluator StateGraph to invoke.
		state: The current parent graph state containing negotiation context.
	Returns:
		A dictionary representing the full validated evaluator response.
	"""
	graph_config = extend_runnable_config(
		config,
		tags=["agent:evaluator", "graph:evaluator"],
		metadata={"agent": "evaluator", "graph": "evaluator"},
		run_name="evaluator.invoke_response",
	)
	result = invoke_with_config(evaluator_graph, state, graph_config)
	return result.get("evaluator_response", {})


@traceable
def invoke_compact_evaluation(
	evaluator_graph: Any,
	state: ParentNegotiationState,
	config: RunnableConfig | None = None,
) -> Evaluation:
	"""
	Invoke the evaluator graph and return only compact Evaluation.
	Args:
		evaluator_graph: The compiled evaluator StateGraph to invoke.
		state: The current parent graph state containing negotiation context.
	Returns:
		A compact Evaluation dictionary.
	"""
	graph_config = extend_runnable_config(
		config,
		tags=["agent:evaluator", "graph:evaluator"],
		metadata={"agent": "evaluator", "graph": "evaluator"},
		run_name="evaluator.invoke_compact",
	)
	result = invoke_with_config(evaluator_graph, state, graph_config)
	return result.get("evaluation", {})
