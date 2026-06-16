from typing import Any
from langchain_core.runnables.config import RunnableConfig
from langsmith import traceable
# local imports
from app.airag.chains.agents.helpers import json_dumps

from app.airag.chains.agents.counterpart.counterpart_model import (
    CounterpartResponseModel,
    CounterpartGraphState
)
from app.airag.chains.agents.counterpart.counterpart_helpers import (
    get_counterpart_side,
    collect_missing_information,
    render_counterpart_prompt,
    coerce_counterpart_response,
    fallback_counterpart_response,
)
from app.airag.observability.llm_usage import extend_runnable_config, invoke_with_config


def node_prepare_counterpart_context(state: CounterpartGraphState) -> dict:
	"""
	Prepare the counterpart context for response generation.
	Args:
		state: The current graph state containing negotiation context.
	Returns:
		A dictionary with the prepared counterpart context, including side,
		messages, offer history, retry count, validation error, missing 
		information, and event log.
	"""
	counterpart_side = get_counterpart_side(state)
	prepared_state = {**state, "counterpart_side": counterpart_side}
	missing_information = collect_missing_information(prepared_state)

	return {
		"counterpart_side": counterpart_side,
		"messages": state.get("messages", []),
		"offer_history": state.get("offer_history", []),
		"counterpart_retry_count": state.get("counterpart_retry_count", 0),
		"counterpart_validation_error": "",
		"missing_information": missing_information,
		"event_log": [
			f"counterpart:prepared_context side={counterpart_side} missing={','.join(missing_information) or 'none'}"
		],
	}


def make_generate_counterpart_response_node(
	model: Any,
	prompt_template: str | None = None,
):
	@traceable
	def node_generate_counterpart_response(
		state: CounterpartGraphState,
		config: RunnableConfig | None = None,
	) -> dict:
		"""
		Generate a counterpart response using the provided model and prompt 
		template.
		Args:
			state: The current graph state containing negotiation context.
		Returns:
			A dictionary with the generated counterpart response, validation 
			error, and event log.
		"""
		if model is None:
			return {
				"counterpart_validation_error": "Counterpart model is not configured.",
				"event_log": ["counterpart:generation_failed"],
			}

		prompt = render_counterpart_prompt(state, prompt_template)
		try:
			structured_model = model.with_structured_output(
				CounterpartResponseModel,
				method="function_calling",
			)
			invoke_config = extend_runnable_config(
				config,
				tags=["agent:counterpart", "node:generate", "prompt:counterpart"],
				metadata={
					"agent": "counterpart",
					"node": "generate",
					"prompt": "counterpart",
				},
				run_name="counterpart.generate",
			)
			response = coerce_counterpart_response(
				invoke_with_config(structured_model, prompt, invoke_config)
			)
		except Exception as exc:
			return {
				"counterpart_prompt": prompt,
				"counterpart_validation_error": str(exc),
				"event_log": ["counterpart:generation_failed"],
			}

		return {
			"counterpart_prompt": prompt,
			"counterpart_response": response,
			"counterpart_validation_error": "",
			"event_log": ["counterpart:generated_response"],
		}

	return node_generate_counterpart_response


def make_repair_counterpart_response_node(
	model: Any,
	prompt_template: str | None = None,
):
	@traceable
	def node_repair_counterpart_response(
		state: CounterpartGraphState,
		config: RunnableConfig | None = None,
	) -> dict:
		"""
		Repair the counterpart response using the provided model and 
		prompt template.
		Args:
			state: The current graph state containing negotiation context.
		Returns:
			A dictionary with the repaired counterpart response, 
			validation error, retry count, and event log.
		"""
		retry_count = state.get("counterpart_retry_count", 0) + 1
		if model is None:
			return {
				"counterpart_retry_count": retry_count,
				"counterpart_validation_error": "Counterpart model is not configured for repair.",
				"event_log": ["counterpart:repair_failed"],
			}

		repair_prompt = "\n\n".join(
			[
				"Repair the counterpart response so it satisfies the required schema.",
				"Return only the structured output. Do not add markdown or commentary.",
				f"Validation or generation error:\n{state.get('counterpart_validation_error', '')}",
				f"Original counterpart prompt:\n{state.get('counterpart_prompt') or render_counterpart_prompt(state, prompt_template)}",
			]
		)

		try:
			structured_model = model.with_structured_output(
				CounterpartResponseModel,
				method="function_calling",
			)
			invoke_config = extend_runnable_config(
				config,
				tags=["agent:counterpart", "node:repair", "prompt:counterpart"],
				metadata={
					"agent": "counterpart",
					"node": "repair",
					"prompt": "counterpart",
				},
				run_name="counterpart.repair",
			)
			response = coerce_counterpart_response(
				invoke_with_config(structured_model, repair_prompt, invoke_config)
			)
		except Exception as exc:
			return {
				"counterpart_retry_count": retry_count,
				"counterpart_validation_error": str(exc),
				"event_log": ["counterpart:repair_failed"],
			}

		return {
			"counterpart_response": response,
			"counterpart_validation_error": "",
			"counterpart_retry_count": retry_count,
			"event_log": ["counterpart:repaired_response"],
		}

	return node_repair_counterpart_response


def node_fallback_counterpart_response(state: CounterpartGraphState) -> dict:
	"""
	Node function to provide a fallback counterpart response when 
	generation or repair fails.
	Args:
		state: The current graph state containing negotiation context.
	Returns:
		A dictionary with the fallback counterpart response and event log.
	"""
	return {
		"counterpart_response": fallback_counterpart_response(
			state,
			state.get("counterpart_validation_error", "unknown counterpart generation failure"),
		),
		"event_log": ["counterpart:fallback"],
	}


def node_finalize_counterpart(state: CounterpartGraphState) -> dict:
	"""
	Node function to finalize the counterpart response and update the graph state
	with the response, current offer, and event log.
	Args:
		state: The current graph state containing negotiation context.
	Returns:
		A dictionary with the finalized counterpart response, current 
		offer, and event log.
	"""
	response = state.get("counterpart_response") or fallback_counterpart_response(
		state,
		"missing counterpart_response at finalize",
	)
	side = response.get("side", state.get("counterpart_side", get_counterpart_side(state)))
	message = response.get("message", "")
	offer = response.get("offer", {})
	private_notes = response.get("private_notes", {})

	updates: dict[str, Any] = {
		"counterpart_response": response,
		"current_offer": offer,
		"event_log": [
			f"counterpart:private_notes {json_dumps(private_notes)}",
			"counterpart:completed",
		],
	}

	if side == "side_a":
		updates["side_a_response"] = message
	else:
		updates["side_b_response"] = message

	if offer:
		updates["offer_history"] = [offer]

	return updates


def decide_after_generate(state: CounterpartGraphState) -> str:
	"""
	Node function to decide the next action after generating a 
	counterpart response.
	Args:
		state: The current graph state containing negotiation context.
	Returns:
		A string indicating the next action: "finalize", "repair", 
		or "fallback".
	"""
	if state.get("counterpart_response"):
		return "finalize"
	if state.get("counterpart_retry_count", 0) < 1:
		return "repair"
	return "fallback"


def decide_after_repair(state: CounterpartGraphState) -> str:
	"""
	Node function to decide the next action after attempting to repair a 
	counterpart response.
	Args:
		state: The current graph state containing negotiation context.
	Returns:
		A string indicating the next action: "finalize" or "fallback".
	"""
	if state.get("counterpart_response"):
		return "finalize"
	return "fallback"
