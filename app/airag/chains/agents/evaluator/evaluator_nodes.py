from typing import Any
# local imports
from app.airag.chains.agents.helpers import json_dumps
from app.airag.chains.agents.evaluator.evaluator_model import (
    EvaluatorGraphState,
	EvaluatorResponseModel,
)
from app.airag.chains.agents.evaluator.evaluator_helpers import (
    get_existing_retrieval_context,
    collect_missing_information,
    build_evaluator_crag_query,
	render_evaluator_prompt,
	coerce_evaluator_response,
	compact_evaluation_from_response,
	fallback_evaluator_response,
)

def node_prepare_evaluator_context(state: EvaluatorGraphState) -> dict:
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
	return {
		"evaluator_query": build_evaluator_crag_query(state),
		"event_log": ["evaluator:selected_crag_query"],
	}


def make_call_crag_node(crag_graph: Any = None):
	def node_call_crag(state: EvaluatorGraphState) -> dict:
		existing_context = get_existing_retrieval_context(state)
		if crag_graph is None:
			return {
				"retrieval_context": existing_context,
				"event_log": ["evaluator:crag_skipped"],
			}

		try:
			result = crag_graph.invoke(
				{
					"question": state.get("evaluator_query", "negotiation evaluation"),
					"attempts": 0,
				}
			)
		except Exception as exc:
			return {
				"retrieval_context": existing_context,
				"evaluator_validation_error": f"CRAG grounding failed: {exc}",
				"event_log": ["evaluator:crag_failed"],
			}

		answer = result.get("answer", "") if isinstance(result, dict) else ""
		context = result.get("context", "") if isinstance(result, dict) else ""
		retrieval_context = "\n\n".join(
			part for part in (answer, context, existing_context) if part
		)

		return {
			"retrieval_context": retrieval_context,
			"event_log": ["evaluator:crag_completed"],
		}

	return node_call_crag


def make_generate_evaluator_response_node(model: Any):
	def node_generate_evaluator_response(state: EvaluatorGraphState) -> dict:
		if model is None:
			return {
				"evaluator_validation_error": "Evaluator model is not configured.",
				"event_log": ["evaluator:generation_failed"],
			}

		prompt = render_evaluator_prompt(state)
		try:
			structured_model = model.with_structured_output(EvaluatorResponseModel)
			response = coerce_evaluator_response(structured_model.invoke(prompt))
		except Exception as exc:
			return {
				"evaluator_prompt": prompt,
				"evaluator_validation_error": str(exc),
				"event_log": ["evaluator:generation_failed"],
			}

		return {
			"evaluator_prompt": prompt,
			"evaluator_response": response,
			"evaluator_validation_error": "",
			"event_log": ["evaluator:generated_response"],
		}

	return node_generate_evaluator_response


def make_repair_evaluator_response_node(model: Any):
	def node_repair_evaluator_response(state: EvaluatorGraphState) -> dict:
		retry_count = state.get("evaluator_retry_count", 0) + 1
		if model is None:
			return {
				"evaluator_retry_count": retry_count,
				"evaluator_validation_error": "Evaluator model is not configured for repair.",
				"event_log": ["evaluator:repair_failed"],
			}

		repair_prompt = "\n\n".join(
			[
				"Repair the evaluator response so it satisfies the required schema.",
				"Return only the structured output. Do not add markdown or commentary.",
				f"Validation or generation error:\n{state.get('evaluator_validation_error', '')}",
				f"Original evaluator prompt:\n{state.get('evaluator_prompt') or render_evaluator_prompt(state)}",
			]
		)

		try:
			structured_model = model.with_structured_output(EvaluatorResponseModel)
			response = coerce_evaluator_response(structured_model.invoke(repair_prompt))
		except Exception as exc:
			return {
				"evaluator_retry_count": retry_count,
				"evaluator_validation_error": str(exc),
				"event_log": ["evaluator:repair_failed"],
			}

		return {
			"evaluator_response": response,
			"evaluator_validation_error": "",
			"evaluator_retry_count": retry_count,
			"event_log": ["evaluator:repaired_response"],
		}

	return node_repair_evaluator_response


def node_fallback_evaluator_response(state: EvaluatorGraphState) -> dict:
	return {
		"evaluator_response": fallback_evaluator_response(
			state,
			state.get("evaluator_validation_error", "unknown evaluator generation failure"),
		),
		"event_log": ["evaluator:fallback"],
	}


def node_finalize_evaluator(state: EvaluatorGraphState) -> dict:
	response = state.get("evaluator_response") or fallback_evaluator_response(
		state,
		"missing evaluator_response at finalize",
	)
	evaluation = compact_evaluation_from_response(state, response)
	next_action = evaluation.get("next_best_action", "ask_user")

	return {
		"evaluator_response": response,
		"evaluation": evaluation,
		"next_action": next_action,
		"event_log": [
			f"evaluator:full_response {json_dumps(response)}",
			"evaluator:completed",
		],
	}


def decide_after_generate(state: EvaluatorGraphState) -> str:
	if state.get("evaluator_response"):
		return "finalize"
	if state.get("evaluator_retry_count", 0) < 1:
		return "repair"
	return "fallback"


def decide_after_repair(state: EvaluatorGraphState) -> str:
	if state.get("evaluator_response"):
		return "finalize"
	return "fallback"
