from typing import Any
from langchain_core.runnables.config import RunnableConfig
from langsmith import traceable
# local imports
from app.airag.chains.agents.helpers import json_dumps
from app.airag.chains.agents.evaluator.evaluator_model import (
    EvaluatorGraphState,
	EvaluatorResponseModel,
	FinalEvaluatorResponseModel,
)
from app.airag.chains.agents.evaluator.evaluator_helpers import (
    build_evaluator_trusted_context,
    get_existing_retrieval_context,
    collect_missing_information,
    build_evaluator_crag_query,
	render_evaluator_prompt,
	render_final_evaluator_prompt,
	coerce_evaluator_response,
	compact_evaluation_from_response,
	fallback_evaluator_response,
	fallback_final_evaluator_response,
	final_evaluation_from_response,
)
from app.airag.observability.evidence_ledger import update_agent_ledger
from app.airag.observability.llm_usage import extend_runnable_config, invoke_with_config

def node_prepare_evaluator_context(state: EvaluatorGraphState) -> dict:
	"""
	Prepare the evaluator context by collecting relevant information from 
	the state.
	Args:
		state: The current evaluator graph state containing negotiation 
			context.
	Returns:
		A dictionary representing the prepared evaluator context.
	"""
	missing_information = collect_missing_information(state)
	return {
		"messages": state.get("messages", []),
		"offer_history": state.get("offer_history", []),
		"coach_advice": state.get("coach_advice", {}),
		"evaluation": state.get("evaluation", {}),
		"retrieval_result": state.get("retrieval_result", {}),
		"evaluator_retry_count": state.get("evaluator_retry_count", 0),
		"evaluator_validation_error": "",
		"missing_information": missing_information,
		"event_log": [
			f"evaluator:prepared_context missing={','.join(missing_information) or 'none'}"
		],
	}


def node_build_evaluator_crag_query(state: EvaluatorGraphState) -> dict:
	"""
	Build a CRAG query for the evaluator based on the current state.
	Args:
		state: The current evaluator graph state containing negotiation 
			context.
	Returns:
		A dictionary with the constructed CRAG query for retrieval.
	"""
	return {
		"evaluator_query": build_evaluator_crag_query(state),
		"event_log": ["evaluator:selected_crag_query"],
	}


def make_call_crag_node(crag_graph: Any = None):
	@traceable
	def node_call_crag(
		state: EvaluatorGraphState,
		config: RunnableConfig | None = None,
	) -> dict:
		"""
		Call the CRAG graph to retrieve additional context for the evaluator.
		Args:
			state: The current evaluator graph state containing negotiation 
				context.
		Returns:
			A dictionary with the retrieval context and event log.
		"""
		existing_context = get_existing_retrieval_context(state)
		if crag_graph is None:
			ledger = update_agent_ledger(
				state,
				agent_name="evaluator",
				step_name="crag",
				status="skipped",
				detail={"query": state.get("evaluator_query", "negotiation evaluation")},
			)
			return {
				"retrieval_context": existing_context,
				"event_log": ["evaluator:crag_skipped"],
				"evidence_ledger": ledger,
			}

		try:
			trusted_context = build_evaluator_trusted_context(state)
			invoke_config = extend_runnable_config(
				config,
				tags=["agent:evaluator", "graph:crag", "node:retrieve_context"],
				metadata={
					"agent": "evaluator",
					"graph": "crag",
					"node": "retrieve_context",
				},
				run_name="evaluator.crag",
			)
			result = invoke_with_config(
				crag_graph,
				{
					"question": state.get("evaluator_query", "negotiation evaluation"),
					"attempts": 0,
					"trusted_context": trusted_context,
				},
				invoke_config,
			)
		except Exception as exc:
			ledger = update_agent_ledger(
				state,
				agent_name="evaluator",
				step_name="crag",
				status="failed",
				detail={
					"query": state.get("evaluator_query", "negotiation evaluation"),
					"error": str(exc),
				},
			)
			return {
				"retrieval_context": existing_context,
				"evaluator_validation_error": f"CRAG grounding failed: {exc}",
				"event_log": ["evaluator:crag_failed"],
				"evidence_ledger": ledger,
			}

		answer = result.get("answer", "") if isinstance(result, dict) else ""
		context = result.get("context", "") if isinstance(result, dict) else ""
		retrieval_context = "\n\n".join(
			part for part in (answer, context, existing_context) if part
		)

		ledger = update_agent_ledger(
			state,
			agent_name="evaluator",
			step_name="crag",
			status="success",
			detail={"query": state.get("evaluator_query", "negotiation evaluation")},
			extra={"crag": result.get("evidence_ledger", {}) if isinstance(result, dict) else {}},
		)
		return {
			"retrieval_context": retrieval_context,
			"event_log": ["evaluator:crag_completed"],
			"evidence_ledger": ledger,
		}

	return node_call_crag


def make_generate_evaluator_response_node(
	model: Any,
	prompt_template: str | None = None,
):
	"""
	Create a node for generating evaluator responses using the specified 
	model and prompt template.
	Args:
		model: The LLM model to use for generating evaluator responses.
		prompt_template: The template to use for rendering the evaluator 
			prompt.
	Returns:
		A function that can be used as a node in the evaluator graph for
		generating evaluator responses.
	"""
	@traceable
	def node_generate_evaluator_response(
		state: EvaluatorGraphState,
		config: RunnableConfig | None = None,
	) -> dict:
		if model is None:
			ledger = update_agent_ledger(
				state,
				agent_name="evaluator",
				step_name="generate",
				status="failed",
				detail={"reason": "model_not_configured"},
			)
			return {
				"evaluator_validation_error": "Evaluator model is not configured.",
				"event_log": ["evaluator:generation_failed"],
				"evidence_ledger": ledger,
			}

		final_mode = state.get("evaluation_mode") == "final"
		prompt = (
			render_final_evaluator_prompt(state, prompt_template)
			if final_mode
			else render_evaluator_prompt(state, prompt_template)
		)
		try:
			schema = FinalEvaluatorResponseModel if final_mode else EvaluatorResponseModel
			structured_model = model.with_structured_output(schema)
			invoke_config = extend_runnable_config(
				config,
				tags=["agent:evaluator", "node:generate", "prompt:evaluator"],
				metadata={"agent": "evaluator", "node": "generate", "prompt": "evaluator"},
				run_name="evaluator.generate",
			)
			response = coerce_evaluator_response(
				invoke_with_config(structured_model, prompt, invoke_config),
				final_mode=final_mode,
			)
		except Exception as exc:
			ledger = update_agent_ledger(
				state,
				agent_name="evaluator",
				step_name="generate",
				status="failed",
				detail={"prompt_chars": len(prompt), "error": str(exc)},
			)
			return {
				"evaluator_prompt": prompt,
				"evaluator_validation_error": str(exc),
				"event_log": ["evaluator:generation_failed"],
				"evidence_ledger": ledger,
			}

		ledger = update_agent_ledger(
			state,
			agent_name="evaluator",
			step_name="generate",
			status="success",
			detail={"prompt_chars": len(prompt)},
			output_summary={
				"kind": "final_evaluation" if final_mode else "rolling_evaluation",
				"confidence": response.get("confidence"),
			},
		)
		return {
			"evaluator_prompt": prompt,
			"evaluator_response": response,
			"evaluator_validation_error": "",
			"event_log": ["evaluator:generated_response"],
			"evidence_ledger": ledger,
		}

	return node_generate_evaluator_response


def make_repair_evaluator_response_node(
	model: Any,
	prompt_template: str | None = None,
):
	@traceable
	def node_repair_evaluator_response(
		state: EvaluatorGraphState,
		config: RunnableConfig | None = None,
	) -> dict:
		"""
		Repair the evaluator response node for failure paths.
		Args:
			state: The current evaluator graph state containing negotiation 
				context.
		Returns:
			A dictionary representation of the repaired evaluator response 
			node.
		"""
		retry_count = state.get("evaluator_retry_count", 0) + 1
		if model is None:
			ledger = update_agent_ledger(
				state,
				agent_name="evaluator",
				step_name="repair",
				status="failed",
				detail={"reason": "model_not_configured"},
			)
			return {
				"evaluator_retry_count": retry_count,
				"evaluator_validation_error": "Evaluator model is not configured for repair.",
				"event_log": ["evaluator:repair_failed"],
				"evidence_ledger": ledger,
			}

		final_mode = state.get("evaluation_mode") == "final"
		repair_prompt = "\n\n".join(
			[
				"Repair the evaluator response so it satisfies the required schema.",
				"Return only the structured output. Do not add markdown or commentary.",
				f"Validation or generation error:\n{state.get('evaluator_validation_error', '')}",
				f"Original evaluator prompt:\n{state.get('evaluator_prompt') or (render_final_evaluator_prompt(state, prompt_template) if final_mode else render_evaluator_prompt(state, prompt_template))}",
			]
		)

		try:
			schema = FinalEvaluatorResponseModel if final_mode else EvaluatorResponseModel
			structured_model = model.with_structured_output(schema)
			invoke_config = extend_runnable_config(
				config,
				tags=["agent:evaluator", "node:repair", "prompt:evaluator"],
				metadata={"agent": "evaluator", "node": "repair", "prompt": "evaluator"},
				run_name="evaluator.repair",
			)
			response = coerce_evaluator_response(
				invoke_with_config(structured_model, repair_prompt, invoke_config),
				final_mode=final_mode,
			)
		except Exception as exc:
			ledger = update_agent_ledger(
				state,
				agent_name="evaluator",
				step_name="repair",
				status="failed",
				detail={"prompt_chars": len(repair_prompt), "error": str(exc)},
			)
			return {
				"evaluator_retry_count": retry_count,
				"evaluator_validation_error": str(exc),
				"event_log": ["evaluator:repair_failed"],
				"evidence_ledger": ledger,
			}

		ledger = update_agent_ledger(
			state,
			agent_name="evaluator",
			step_name="repair",
			status="success",
			detail={"prompt_chars": len(repair_prompt)},
			output_summary={
				"kind": "final_evaluation" if final_mode else "rolling_evaluation",
				"confidence": response.get("confidence"),
			},
		)
		return {
			"evaluator_response": response,
			"evaluator_validation_error": "",
			"evaluator_retry_count": retry_count,
			"event_log": ["evaluator:repaired_response"],
			"evidence_ledger": ledger,
		}

	return node_repair_evaluator_response


def node_fallback_evaluator_response(state: EvaluatorGraphState) -> dict:
	"""
	Build a fallback evaluator response node for failure paths.
	Args:
		state: The current evaluator graph state containing negotiation 
			context.
	Returns:
		A dictionary representation of the fallback evaluator response node.
	"""
	final_mode = state.get("evaluation_mode") == "final"
	response = (
		fallback_final_evaluator_response(
			state,
			state.get(
				"evaluator_validation_error",
				"unknown final evaluator generation failure",
			),
		)
		if final_mode
		else fallback_evaluator_response(
			state,
			state.get(
				"evaluator_validation_error",
				"unknown evaluator generation failure",
			),
		)
	)
	ledger = update_agent_ledger(
		state,
		agent_name="evaluator",
		step_name="fallback",
		status="used",
		output_summary={
			"kind": "final_evaluation" if final_mode else "rolling_evaluation",
			"confidence": response.get("confidence"),
		},
	)
	return {
		"evaluator_response": response,
		"event_log": ["evaluator:fallback"],
		"evidence_ledger": ledger,
	}


def node_finalize_evaluator(state: EvaluatorGraphState) -> dict:
	"""
	Finalize the evaluator response node.
	Args:
		state: The current graph state containing negotiation context.
	Returns:
		A dictionary representation of the finalized evaluator response node.
	"""
	final_mode = state.get("evaluation_mode") == "final"
	response = state.get("evaluator_response") or (
		fallback_final_evaluator_response(
			state,
			"missing evaluator_response at finalize",
		)
		if final_mode
		else fallback_evaluator_response(
			state,
			"missing evaluator_response at finalize",
		)
	)

	updates = {
		"evaluator_response": response,
		"event_log": [
			f"evaluator:full_response {json_dumps(response)}",
			"evaluator:completed",
		],
		"evidence_ledger": update_agent_ledger(
			state,
			agent_name="evaluator",
			step_name="finalize",
			status="success",
			output_summary={
				"kind": "final_evaluation" if final_mode else "rolling_evaluation",
				"confidence": response.get("confidence"),
			},
		),
	}
	if final_mode:
		updates["final_evaluation"] = final_evaluation_from_response(state, response)
	else:
		updates["evaluation"] = compact_evaluation_from_response(state, response)
	return updates


def decide_after_generate(state: EvaluatorGraphState) -> str:
	"""
	Decide the next action after generating an evaluator response.
	Args:
		state: The current graph state containing negotiation context.
	Returns:
		A string indicating the next node to transition to based on the
		presence and validity of the evaluator response.
	"""
	if state.get("evaluator_response"):
		return "finalize"
	if state.get("evaluator_retry_count", 0) < 1:
		return "repair"
	return "fallback"


def decide_after_repair(state: EvaluatorGraphState) -> str:
	"""
	Decide the next action after attempting to repair an evaluator response.
	Args:
		state: The current graph state containing negotiation context.
	Returns:
		A string indicating the next node to transition to based on the
		presence and validity of the evaluator response.
	"""
	if state.get("evaluator_response"):
		return "finalize"
	return "fallback"
