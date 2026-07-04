from typing import Any
from langchain_core.runnables.config import RunnableConfig
### --------------------- COACH SPECIFIC NODES --------------------- ###
from langsmith import traceable

# local imports
from app.airag.chains.agents.coach.coach_helpers import (
    build_rag_query,
    build_coach_trusted_context,
    fallback_advice,
    render_coach_prompt,
	collect_missing_information,
)
from app.airag.chains.agents.helpers import json_dumps, format_messages
from app.airag.chains.agents.coach.coach_model import CoachGraphState, CoachAdviceModel
from app.airag.observability.evidence_ledger import extract_source_cards, update_agent_ledger
from app.airag.observability.llm_usage import extend_runnable_config, invoke_with_config


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


def node_route_rag_queries(state: CoachGraphState) -> dict:
	"""
	Node function to build and route RAG queries based on the current state, 
	emphasizing key negotiation details and any missing information that 
	could be relevant for retrieval.
	Args:
        state: The current state of the coach graph, containing all relevant
            information about the negotiation.
	Returns:
        A dictionary containing the constructed coach query for RAG, and an 
		    event log entry describing the routing step.
	"""
	return {
		"coach_query": build_rag_query(state),
		"event_log": ["coach:selected_rag_query"],
	}


def make_call_rag_node(rag_graph: Any, retrieval_strategy: str = "crag"):
	"""
	Factory function to create a node function that calls the RAG graph 
	with the constructed query and updates the retrieval context based on 
	the results.
	Args:
		rag_graph: The RAG graph to use for context retrieval.
		retrieval_strategy: The strategy to use for retrieving information 
			from RAG, either "crag" or "graphrag".
	Returns:
		A node function that takes the current coach graph state, invokes the
		RAG graph with the constructed query, and returns the updated
		retrieval context along with any validation errors, event log entries
		describing the RAG invocation, and an updated evidence ledger.
	"""
	retrieval_key = "graphrag" if retrieval_strategy == "graphrag" else "crag"
	retrieval_label = "GraphRAG" if retrieval_key == "graphrag" else "CRAG"

	@traceable
	def node_call_rag(
		state: CoachGraphState,
		config: RunnableConfig | None = None,
	) -> dict:
		"""
		Node function to call the RAG graph with the constructed query
		and update the retrieval context based on the results.
		Args:
            state: The current state of the coach graph, containing all relevant
                information about the negotiation, including the constructed coach query.
        Returns:
            A dictionary containing the updated retrieval context based on the 
			RAG results, any validation errors, event log entries describing 
			the RAG invocation, and an updated evidence ledger.
		"""
		if rag_graph is None:
			ledger = update_agent_ledger(
				state,
				agent_name="coach",
				step_name=retrieval_key,
				status="skipped",
				detail={"query": state.get("coach_query", "")},
			)
			return {
				"retrieval_context": state.get("retrieval_context", ""),
				"event_log": [f"coach:{retrieval_key}_skipped"],
				"evidence_ledger": ledger,
			}

		try: 
			trusted_context = build_coach_trusted_context(state)
			invoke_config = extend_runnable_config(
				config,
				tags=["agent:coach", f"graph:{retrieval_key}", "node:retrieve_context"],
				metadata={
					"agent": "coach",
					"graph": retrieval_key,
					"node": "retrieve_context",
				},
				run_name=f"coach.{retrieval_key}",
			)
			result = invoke_with_config(
				rag_graph,
				{
					"question": state.get("coach_query", ""),
					"attempts": 0,
					"trusted_context": trusted_context,
				},
				invoke_config,
			)
		except Exception as exc:
			ledger = update_agent_ledger( # Update the coach's ledger with the RAG invocation failure
				state,
				agent_name="coach",
				step_name=retrieval_key,
				status="failed",
				detail={"query": state.get("coach_query", ""), "error": str(exc)},
			)
			return {
				"retrieval_context": state.get("retrieval_context", ""),
				"coach_validation_error": f"{retrieval_label} invocation failed: {exc}",
				"event_log": [f"coach:{retrieval_key}_failed"],
				"evidence_ledger": ledger,
			}

		answer = result.get("answer", "") if isinstance(result, dict) else ""
		context = result.get("context", "") if isinstance(result, dict) else ""
		retrieval_context = "\n\n".join(part for part in [answer, context] if part)
		if not retrieval_context:
			retrieval_context = state.get("retrieval_context", "")

		ledger = update_agent_ledger( # Update the coach's ledger with the successful RAG invocation
			state,
			agent_name="coach",
			step_name=retrieval_key,
			status="success",
			detail={"query": state.get("coach_query", "")},
			extra={retrieval_key: result.get("evidence_ledger", {}) if isinstance(result, dict) else {}},
		)
		sources = (
			extract_source_cards(result.get("evidence_ledger", {}))
			if isinstance(result, dict)
			else []
		)
		return {
			"retrieval_context": retrieval_context,
			"sources": sources,
			"event_log": [f"coach:{retrieval_key}_completed"],
			"evidence_ledger": ledger,
		}

	return node_call_rag


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
			generated advice along with any validation errors, event log 
			entries describing the generation step, and an updated evidence 
			ledger.
	"""
	@traceable
	def node_generate_coach_advice(
		state: CoachGraphState,
		config: RunnableConfig | None = None,
	) -> dict:
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
				"evidence_ledger": dict,
            }
		"""

		if model is None:
			ledger = update_agent_ledger(
				state,
				agent_name="coach",
				step_name="generate",
				status="failed",
				detail={"reason": "model_not_configured"},
			)
			return {
				"coach_validation_error": "Coach model is not configured.",
				"event_log": ["coach:generation_failed"],
				"evidence_ledger": ledger,
			}

		prompt = render_coach_prompt(state, prompt_template)
		try:
			structured_model = model.with_structured_output(CoachAdviceModel)
			invoke_config = extend_runnable_config(
				config,
				tags=["agent:coach", "node:generate", "prompt:coach"],
				metadata={"agent": "coach", "node": "generate", "prompt": "coach"},
				run_name="coach.generate",
			)
			advice = invoke_with_config(structured_model, prompt, invoke_config)
			advice_payload = advice.model_dump()
			ledger = update_agent_ledger(
				state,
				agent_name="coach",
				step_name="generate",
				status="success",
				detail={"prompt_chars": len(prompt)},
				output_summary={
					"kind": "coach_advice",
					"confidence": advice_payload.get("confidence"),
				},
			)
			return {
				"coach_prompt": prompt,
				"coach_advice": advice_payload,
				"coach_validation_error": "",
				"event_log": ["coach:generated_advice"],
				"evidence_ledger": ledger,
			}
		except Exception as exc: # Catch any exceptions during model invocation and return a structured failure payload to the ledger
			ledger = update_agent_ledger( 
				state,
				agent_name="coach",
				step_name="generate",
				status="failed",
				detail={"prompt_chars": len(prompt), "error": str(exc)},
			)
			return {
				"coach_prompt": prompt,
				"coach_validation_error": str(exc),
				"event_log": ["coach:generation_failed"],
				"evidence_ledger": ledger,
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
	@traceable
	def node_repair_coach_advice(
		state: CoachGraphState,
		config: RunnableConfig | None = None,
	) -> dict:
		"""
		Node function to attempt to repair coach advice generation failures by 
		re-invoking the model with a focused prompt that includes validation 
		errors and emphasizes the importance of adhering to the 
		CoachAdviceModel schema.
        Args:
            state: The current state of the coach graph, containing all 
			    relevant information about the negotiation, the original 
				    coach prompt, any validation errors from the initial 
					generation attempt, and updated coach ledger.
        Returns:
            A dictionary containing the repaired coach advice if generation 
			is successful, any validation errors if the repair attempt also 
			fails, and event log entries describing the repair step.
            {
                "coach_advice": dict,
                "coach_validation_error": str,
                "coach_retry_count": int,
                "event_log": list[str],
				"evidence_ledger": dict,
            }
		"""
		if model is None:
			ledger = update_agent_ledger(
				state,
				agent_name="coach",
				step_name="repair",
				status="failed",
				detail={"reason": "model_not_configured"},
			)
			return {
				"coach_retry_count": state.get("coach_retry_count", 0) + 1,
				"event_log": ["coach:repair_skipped"],
				"evidence_ledger": ledger,
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
			invoke_config = extend_runnable_config(
				config,
				tags=["agent:coach", "node:repair", "prompt:coach"],
				metadata={"agent": "coach", "node": "repair", "prompt": "coach"},
				run_name="coach.repair",
			)
			advice = invoke_with_config(structured_model, repair_prompt, invoke_config)
			advice_payload = advice.model_dump()
			ledger = update_agent_ledger(
				state,
				agent_name="coach",
				step_name="repair",
				status="success",
				detail={"prompt_chars": len(repair_prompt)},
				output_summary={
					"kind": "coach_advice",
					"confidence": advice_payload.get("confidence"),
				},
			)
			return {
				"coach_advice": advice_payload,
				"coach_validation_error": "",
				"coach_retry_count": state.get("coach_retry_count", 0) + 1,
				"event_log": ["coach:repaired_advice"],
				"evidence_ledger": ledger,
			}
		except Exception as exc: # Log the repair failure in the coach's ledger
			ledger = update_agent_ledger( 
				state,
				agent_name="coach",
				step_name="repair",
				status="failed",
				detail={"prompt_chars": len(repair_prompt), "error": str(exc)},
			)
			return {
				"coach_validation_error": str(exc),
				"coach_retry_count": state.get("coach_retry_count", 0) + 1,
				"event_log": ["coach:repair_failed"],
				"evidence_ledger": ledger,
			}

	return node_repair_coach_advice


def node_fallback_coach_advice(state: CoachGraphState) -> dict:
	"""
	Node function to provide fallback coach advice when all other generation and repair attempts have been exhausted, ensuring that the coach can still provide some level of guidance to the user even when ideal generation fails.
    Args:
        state: The current state of the coach graph, containing all relevant 
            information about the negotiation, the original coach prompt,
            any validation errors from previous generation attempts, and
			updated coach ledger.
    Returns:
        A dictionary containing generic fallback coach advice that provides 
		safe and actionable guidance to the user, an explanation of the 
		limitations of the advice, and event log entries describing the 
		fallback step.
        {
            "coach_advice": dict,
            "event_log": list[str],
			"evidence_ledger": dict,
        }	
	"""
	advice = fallback_advice(
		state,
		state.get("coach_validation_error", "unknown coach generation failure"),
	)
	ledger = update_agent_ledger( # Update the coach's ledger with the fallback advice usage
		state,
		agent_name="coach",
		step_name="fallback",
		status="used",
		output_summary={
			"kind": "coach_advice",
			"confidence": advice.get("confidence"),
		},
	)
	return {
		"coach_advice": advice,
		"event_log": ["coach:fallback"],
		"evidence_ledger": ledger,
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
		the generated advice or fallback advice if validation failed), 
		event log entries describing the finalization step and the updated 
		evidence ledger.
        {
            "coach_advice": dict,
            "event_log": list[str],
			"evidence_ledger": dict,
        }	
	"""
	if state.get("coach_advice"):
		advice = dict(state["coach_advice"])
		if state.get("sources"):
			advice["sources"] = state["sources"]
		ledger = update_agent_ledger(
			state,
			agent_name="coach",
			step_name="finalize",
			status="success",
			output_summary={
				"kind": "coach_advice",
				"confidence": advice.get("confidence"),
			},
		)
		return {
			"coach_advice": advice,
			"event_log": ["coach:completed"],
			"evidence_ledger": ledger,
		}

	advice = fallback_advice(state, "missing coach_advice at finalize")
	if state.get("sources"):
		advice["sources"] = state["sources"]
	ledger = update_agent_ledger(
		state,
		agent_name="coach",
		step_name="fallback",
		status="used",
		output_summary={
			"kind": "coach_advice",
			"confidence": advice.get("confidence"),
		},
	)
	return {
		"coach_advice": advice,
		"event_log": ["coach:fallback_at_finalize"],
		"evidence_ledger": ledger,
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
