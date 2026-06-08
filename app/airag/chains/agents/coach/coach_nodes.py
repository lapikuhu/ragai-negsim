from typing import Any
### --------------------- COACH SPECIFIC NODES --------------------- ###

# local imports
from app.airag.chains.agents.coach.coach_helpers import (
    build_crag_query,
    fallback_advice,
    render_coach_prompt,
	collect_missing_information,
)
from app.airag.chains.agents.helpers import json_dumps, format_messages
from app.airag.chains.agents.coach.coach_model import CoachGraphState, CoachAdviceModel


def node_prepare_coach_context(state: CoachGraphState) -> dict:
	"""
	Node function to prepare the coach context by extracting relevant 
	information from the state and identifying any missing information that 
	may impact coach advice generation.
    Args:
        state: The current state of the coach graph, containing all relevant 
		    information about the negotiation.
    Returns:
        A dictionary containing the prepared retrieval context for the coach, 
		    an updated coach retry count, any validation errors, and an event 
			log entry describing the preparation step.
	"""
	missing_information = collect_missing_information(state)
	return {
		"retrieval_context": "",
		"coach_retry_count": state.get("coach_retry_count", 0),
		"coach_validation_error": "",
		"event_log": [
			f"coach:prepared_context missing={','.join(missing_information) or 'none'}"
		],
	}


def node_route_crag_queries(state: CoachGraphState) -> dict:
	"""
	Node function to build and route CRAG queries based on the current state, 
	emphasizing key negotiation details and any missing information that 
	could be relevant for retrieval.
	Args:
        state: The current state of the coach graph, containing all relevant
            information about the negotiation.
	Returns:
        A dictionary containing the constructed coach query for CRAG, and an 
		    event log entry describing the routing step.
	"""
	return {
		"coach_query": build_crag_query(state),
		"event_log": ["coach:selected_crag_query"],
	}


def make_call_crag_node(crag_graph: Any):
	"""
	Factory function to create a node function that calls the CRAG graph 
	with the constructed query and updates the retrieval context based on 
	the results."""
	def node_call_crag(state: CoachGraphState) -> dict:
		"""
		Node function to call the CRAG graph with the constructed query
		and update the retrieval context based on the results.
		Args:
            state: The current state of the coach graph, containing all relevant
                information about the negotiation, including the constructed coach query.
        Returns:
            A dictionary containing the updated retrieval context based on the 
			CRAG results, any validation errors, and event log entries 
			describing the CRAG invocation.  
		"""
		if crag_graph is None:
			return {
				"retrieval_context": state.get("retrieval_context", ""),
				"event_log": ["coach:crag_skipped"],
			}

		try:
			result = crag_graph.invoke(
				{
					"question": state.get("coach_query", ""),
					"attempts": 0,
				}
			)
		except Exception as exc:
			return {
				"retrieval_context": state.get("retrieval_context", ""),
				"coach_validation_error": f"CRAG invocation failed: {exc}",
				"event_log": ["coach:crag_failed"],
			}

		answer = result.get("answer", "") if isinstance(result, dict) else ""
		context = result.get("context", "") if isinstance(result, dict) else ""
		retrieval_context = "\n\n".join(part for part in [answer, context] if part)
		if not retrieval_context:
			retrieval_context = state.get("retrieval_context", "")

		return {
			"retrieval_context": retrieval_context,
			"event_log": ["coach:crag_completed"],
		}

	return node_call_crag


def make_generate_coach_advice_node(
	model: Any,
	prompt_template: str | None = None,
):
	"""
	Factory function to create a node function that generates coach advice 
	using the specified LLM model, with structured output validation and 
	error handling.
    Args:
        model: The LLM model to use for generating coach advice, which should 
		    support structured output validation against the CoachAdviceModel 
		    schema.
    Returns:
        A node function that takes the current coach graph state, renders the 
		    coach prompt, invokes the model to generate advice, validates the 
		    output against the CoachAdviceModel schema, and returns the 
			generated advice along with any validation errors and event log 
			entries describing the generation step.
	"""
	def node_generate_coach_advice(state: CoachGraphState) -> dict:
		"""
		Node function to generate coach advice using the specified LLM model, 
		with structured output validation and error handling.
        Args:
            state: The current state of the coach graph, containing all 
			    relevant information about the negotiation and the rendered 
				coach prompt.
		Returns:
            A dictionary containing the generated coach advice validated 
			against the CoachAdviceModel schema, any validation errors, and 
			event log entries describing the generation step.
            {
                "coach_prompt": str,
                "coach_advice": dict,
                "coach_validation_error": str,
                "event_log": list[str],
            }
		"""

		if model is None:
			return {
				"coach_validation_error": "Coach model is not configured.",
				"event_log": ["coach:generation_failed"],
			}

		prompt = render_coach_prompt(state, prompt_template)
		try:
			structured_model = model.with_structured_output(CoachAdviceModel)
			advice = structured_model.invoke(prompt)
			return {
				"coach_prompt": prompt,
				"coach_advice": advice.model_dump(),
				"coach_validation_error": "",
				"event_log": ["coach:generated_advice"],
			}
		except Exception as exc:
			return {
				"coach_prompt": prompt,
				"coach_validation_error": str(exc),
				"event_log": ["coach:generation_failed"],
			}

	return node_generate_coach_advice


def make_repair_coach_advice_node(
	model: Any,
	prompt_template: str | None = None,
):
	"""
	Factory function to create a node function that attempts to repair coach 
	advice generation failures by re-invoking the model with a focused prompt 
	that includes validation errors and emphasizes the
	"""
	def node_repair_coach_advice(state: CoachGraphState) -> dict:
		"""
		Node function to attempt to repair coach advice generation failures by 
		re-invoking the model with a focused prompt that includes validation 
		errors and emphasizes the importance of adhering to the 
		CoachAdviceModel schema.
        Args:
            state: The current state of the coach graph, containing all 
			    relevant information about the negotiation, the original 
				    coach prompt, and any validation errors from the initial 
					generation attempt.
        Returns:
            A dictionary containing the repaired coach advice if generation is successful, any validation errors if the repair attempt also fails, and event log entries describing the repair step.
            {
                "coach_advice": dict,
                "coach_validation_error": str,
                "coach_retry_count": int,
                "event_log": list[str],
            }
		"""
		if model is None:
			return {
				"coach_retry_count": state.get("coach_retry_count", 0) + 1,
				"event_log": ["coach:repair_skipped"],
			}

		repair_prompt = "\n\n".join(
			[
				"Repair the coach advice output so it satisfies the required schema.",
				"Return only the structured output. Do not add commentary.",
				f"Validation or generation error:\n{state.get('coach_validation_error', '')}",
				f"Original coach prompt:\n{state.get('coach_prompt') or render_coach_prompt(state, prompt_template)}",
			]
		)

		try:
			structured_model = model.with_structured_output(CoachAdviceModel)
			advice = structured_model.invoke(repair_prompt)
			return {
				"coach_advice": advice.model_dump(),
				"coach_validation_error": "",
				"coach_retry_count": state.get("coach_retry_count", 0) + 1,
				"event_log": ["coach:repaired_advice"],
			}
		except Exception as exc:
			return {
				"coach_validation_error": str(exc),
				"coach_retry_count": state.get("coach_retry_count", 0) + 1,
				"event_log": ["coach:repair_failed"],
			}

	return node_repair_coach_advice


def node_fallback_coach_advice(state: CoachGraphState) -> dict:
	"""
	Node function to provide fallback coach advice when all other generation and repair attempts have been exhausted, ensuring that the coach can still provide some level of guidance to the user even when ideal generation fails.
    Args:
        state: The current state of the coach graph, containing all relevant 
            information about the negotiation, the original coach prompt, and
            any validation errors from previous generation attempts.
    Returns:
        A dictionary containing generic fallback coach advice that provides 
		safe and actionable guidance to the user, an explanation of the 
		limitations of the advice, and event log entries describing the 
		fallback step.
        {
            "coach_advice": dict,
            "event_log": list[str],
        }	
	"""
	return {
		"coach_advice": fallback_advice(
			state,
			state.get("coach_validation_error", "unknown coach generation failure"),
		),
		"event_log": ["coach:fallback"],
	}


def node_finalize_coach(state: CoachGraphState) -> dict:
	"""
	Node function to finalize the coach advice, which in this case simply 
	checks if valid advice has been generated and logs the completion of 
	the coach process. If valid advice is not present, it falls back to 
	generating generic advice.
    Args:
        state: The current state of the coach graph, containing all relevant 
            information about the negotiation and the generated coach advice.
    Returns:
        A dictionary containing the finalized coach advice (which may be 
		the generated advice or fallback advice if validation failed) and 
		event log entries describing the finalization step.
        {
            "coach_advice": dict,
            "event_log": list[str],
        }
	"""
	if state.get("coach_advice"):
		return {"event_log": ["coach:completed"]}

	return {
		"coach_advice": fallback_advice(state, "missing coach_advice at finalize"),
		"event_log": ["coach:fallback_at_finalize"],
	}

### ROUTERS
def decide_after_generate(state: CoachGraphState) -> str:
	"""
	Router function to decide the next step after attempting to generate 
	coach advice, based on whether valid advice was generated or if there 
	were validation errors that warrant a repair attempt.
    Args:
        state: The current state of the coach graph, containing all relevant 
            information about the negotiation, the generated coach advice, and
            any validation errors from the generation attempt.
    Returns:
        A string indicating the next step in the graph: "finalize" if valid 
		advice was generated, "repair" if there were validation errors that 
		could potentially be resolved with a repair attempt, or "fallback" 
		if generation failed and a repair attempt is not warranted.

	"""
	if state.get("coach_advice"):
		return "finalize"
	if state.get("coach_retry_count", 0) < 1:
		return "repair"
	return "fallback"


def decide_after_repair(state: CoachGraphState) -> str:
	"""
	Router function to decide the next step after attempting to repair coach 
	advice, based on whether valid advice was generated from the repair 
	attempt or if there were still validation errors that warrant falling 
	back to generic advice.
    Args:        
	    state: The current state of the coach graph, containing all relevant 
		    information about the negotiation, the generated coach advice from 
		    the repair attempt, and any validation errors from the repair 
			attempt.
    Returns:        
	    A string indicating the next step in the graph: "finalize" if 
		valid advice was generated from the repair attempt, or "fallback" 
		if the repair attempt also failed and a fallback to generic advice 
		is warranted.
	"""
	if state.get("coach_advice"):
		return "finalize"
	return "fallback"
