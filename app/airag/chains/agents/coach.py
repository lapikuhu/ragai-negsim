import json
import operator
from typing import Annotated, Any, Literal
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
from typing_extensions import NotRequired, TypedDict
from langgraph.graph import StateGraph, START, END

# local imports
from app.airag.chains.negotiation.negotiation_model import (
	CoachAdvice,
	Confidence,
	Evaluation,
	Offer,
	ParentNegotiationState,
	RetrievalResult,
	Side,
	SideProfile,
)
from app.airag.prompts.neg_prompts.md_loader import COACH_PROMPT

# 
CoachNextMove = Literal[
	"accept",
	"reject",
	"counter",
	"clarify",
	"pause",
	"escalate",
	"unknown",
]

# Position assessment details that the coach will provide to help 
# the user understand their current standing in relation to their 
# goals and walk-away point.
class PositionAssessmentModel(BaseModel):
	"""Validated position assessment matching coach_prompt.md."""

	target_value: str
	reservation_value: str
	current_offer_assessment: str
	zopa_comment: str

# The coach advise model
class CoachAdviceModel(BaseModel):
	"""Validated coach advice matching CoachAdvice."""

	target_side: Side
	summary: str
	position_assessment: PositionAssessmentModel
	risks: list[str] = Field(default_factory=list)
	recommended_next_move: CoachNextMove | str
	suggested_response: str
	reasoning: str
	confidence: Confidence
	missing_information: list[str] = Field(default_factory=list)

# The state schema for the coach graph, which will be used to validate the 
# state.
class CoachGraphState(TypedDict, total=False):
	"""State consumed and produced by the coach graph."""

	session_id: str
	user_id: str
	user_side: Side
	side_a: SideProfile
	side_b: SideProfile
	messages: list[Any]
	phase: str
	active_side: Side
	current_offer: Offer
	offer_history: list[Offer]
	coach_advice: CoachAdvice
	side_a_response: str
	side_b_response: str
	evaluation: Evaluation
	retrieval_result: RetrievalResult
	next_action: str
	turn_count: int
	event_log: NotRequired[Annotated[list[str], operator.add]]

	coach_query: str
	retrieval_context: str
	coach_prompt: str
	coach_validation_error: str
	coach_retry_count: int

### --------------------------- HELPERS ---------------------------- ###
def _json_dumps(value: Any) -> str:
	"""Serialize prompt values compactly while tolerating LangChain objects."""
	return json.dumps(value, default=str, ensure_ascii=False, indent=2)


def _format_messages(messages: list[Any] | None) -> str:
	"""
	Format messages for inclusion in the coach prompt, handling LangChain message objects gracefully.
	Args:
        messages: A list of messages, which may include LangChain BaseMessage objects or plain dicts.
    Returns:
        A string representation of the messages suitable for inclusion in the coach prompt.
	"""
	if not messages:
		return "[]"

	formatted_messages = []
	for message in messages:
		if isinstance(message, BaseMessage):
			formatted_messages.append(
				{
					"type": message.type,
					"content": message.content,
				}
			)
		else:
			formatted_messages.append(message)

	return _json_dumps(formatted_messages)


def _render_coach_prompt(state: CoachGraphState) -> str:
	"""Render the coach prompt by replacing placeholders with current state values.
	Args:
        state: The current state of the coach graph, containing all relevant information about the negotiation.
    Returns:
        A string containing the rendered coach prompt ready to be sent to the LLM.
	"""
	replacements = {
		"{user_side}": state.get("user_side", ""),
		"{side_a_profile}": _json_dumps(state.get("side_a", {})),
		"{side_b_profile}": _json_dumps(state.get("side_b", {})),
		"{phase}": state.get("phase", ""),
		"{active_side}": state.get("active_side", ""),
		"{messages}": _format_messages(state.get("messages", [])),
		"{current_offer}": _json_dumps(state.get("current_offer", {})),
		"{offer_history}": _json_dumps(state.get("offer_history", [])),
		"{retrieval_context}": state.get("retrieval_context", ""),
		"{evaluation}": _json_dumps(state.get("evaluation", {})),
	}

	prompt = COACH_PROMPT
	for placeholder, value in replacements.items():
		prompt = prompt.replace(placeholder, str(value))
	return prompt


def _get_user_profile(state: CoachGraphState) -> SideProfile:
	"""
	Helper function to extract the user-controlled side's profile from the 
	state.
	Args:
        state: The current state of the coach graph, containing all relevant 
		    information about the negotiation.
    Returns:
        A SideProfile object containing the profile information of the 
		    user-controlled side.
	"""
	if state.get("user_side") == "side_b":
		return state.get("side_b", {})
	return state.get("side_a", {})


def _get_existing_retrieval_context(state: CoachGraphState) -> str:
	"""
	Helper function to extract any existing retrieval context from the 
	state.
	Args:
        state: The current state of the coach graph, containing all relevant
            information about the negotiation.
    Returns:
        A string containing the existing retrieval context, or an empty string
            if no context is available.
	"""
	retrieval_result = state.get("retrieval_result", {})
	return retrieval_result.get("summary", "") if isinstance(retrieval_result, dict) else ""


def _collect_missing_information(state: CoachGraphState) -> list[str]:
	"""
	Helper function to collect information about missing or incomplete state fields that may be relevant for coach advice generation and validation.
    Args:    
	    state: The current state of the coach graph, containing all relevant 
		    information about the negotiation.
    Returns:    
	    A list of strings describing missing or incomplete information in the 
		    state that may impact coach advice generation or validation.
    """
	missing = []
	user_side = state.get("user_side")
	user_profile = _get_user_profile(state)

	if not user_side:
		missing.append("user_side")
	if not state.get("current_offer"):
		missing.append("current_offer")
	if not state.get("offer_history"):
		missing.append("offer_history")
	if "target_value" not in user_profile:
		missing.append("user_profile.target_value")
	if "reservation_value" not in user_profile:
		missing.append("user_profile.reservation_value")
	if "value_preference" not in user_profile:
		missing.append("user_profile.value_preference")

	return missing


def _build_crag_query(state: CoachGraphState) -> str:
	"""
	Helper function to build a focused CRAG query based on the current 
	state, emphasizing missing information and key negotiation details that
	the coach can use to provide relevant advice.
	Args:
        state: The current state of the coach graph, containing all relevant
            information about the negotiation.
	Returns:
        A string containing a focused CRAG query that the coach can use to 
            retrieve relevant information for advice generation.
	"""
	user_side = state.get("user_side", "the user-controlled side")
	phase = state.get("phase", "unknown")
	current_offer = state.get("current_offer", {})
	offer_history = state.get("offer_history", [])
	evaluation = state.get("evaluation", {})
	user_profile = _get_user_profile(state)
	query_parts = [
		"Provide concise negotiation theory and tactics for coaching a user.",
		f"The user controls {user_side}. The negotiation phase is {phase}.",
	]

	if not current_offer:
		query_parts.append(
			"Focus on clarifying missing offer information and asking useful questions."
		)
	else:
		query_parts.append(f"Current offer: {_json_dumps(current_offer)}")

	if "target_value" in user_profile or "reservation_value" in user_profile:
		query_parts.append(
			"Discuss target values, reservation values, BATNA protection, and concession strategy."
		)

	if len(offer_history) > 1:
		query_parts.append(
			"Discuss concession patterns, anchoring, momentum, and avoiding premature concessions."
		)

	detected_risks = evaluation.get("detected_risks", []) if isinstance(evaluation, dict) else []
	if detected_risks:
		query_parts.append(f"Known risks to address: {_json_dumps(detected_risks)}")

	return "\n".join(query_parts)


def _fallback_advice(state: CoachGraphState, reason: str) -> CoachAdvice:
	"""
	Helper function to generate fallback coach advice when validation or 
	generation fails, providing safe and generic guidance while indicating the 
	limitations of the advice.
	Args:
        state: The current state of the coach graph, containing all relevant
            information about the negotiation.
		reason: A string describing the reason for the fallback, such as 
		    validation errors or generation failures.
    Returns:
        A CoachAdvice object containing generic fallback advice and an 
            explanation of the limitations.
	"""
	user_side = state.get("user_side", "side_a")
	if user_side not in {"side_a", "side_b"}:
		user_side = "side_a"

	missing_information = _collect_missing_information(state)
	if reason:
		missing_information.append(f"coach_generation_error: {reason}")

	return {
		"target_side": user_side,
		"summary": "Coach advice could not be generated safely from the available state.",
		"position_assessment": {
			"target_value": "unknown",
			"reservation_value": "unknown",
			"current_offer_assessment": "unknown",
			"zopa_comment": "unknown",
		},
		"risks": ["The coach output failed validation or generation."],
		"recommended_next_move": "clarify",
		"suggested_response": "Could you clarify the current offer, key terms, and your walk-away point before making the next move?",
		"reasoning": "The graph returned fallback advice because it could not validate a complete coach response.",
		"confidence": "low",
		"missing_information": missing_information,
	}


def _get_default_coach_model() -> Any | None:
	"""
	Helper function to get a default LLM model for the coach if one is 
	not provided, with error handling to ensure the graph can still function 
	even if no model is available.
	Args:
        None
    Returns:
        An LLM model instance configured for the coach, or None if no model
        could be loaded, allowing the graph to handle the absence of a model
		gracefully.

	"""
	try:
		from app.airag.llm_models.llm_models import get_openai_llm

		return get_openai_llm("gpt-4o", temperature=0.0)
	except Exception:
		try:
			from langchain_openai import ChatOpenAI

			return ChatOpenAI(model="gpt-4o", temperature=0.0)
		except Exception:
			return None
### ------------------- END OF HELPER FUNCTIONS -------------------- ###


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
	missing_information = _collect_missing_information(state)
	retrieval_context = _get_existing_retrieval_context(state)
	return {
		"retrieval_context": retrieval_context,
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
		"coach_query": _build_crag_query(state),
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


def make_generate_coach_advice_node(model: Any):
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

		prompt = _render_coach_prompt(state)
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


def make_repair_coach_advice_node(model: Any):
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
				f"Original coach prompt:\n{state.get('coach_prompt') or _render_coach_prompt(state)}",
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
		"coach_advice": _fallback_advice(
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
		"coach_advice": _fallback_advice(state, "missing coach_advice at finalize"),
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

### -------------- END OF NODE AND ROUTER FUNCTIONS ---------------- ###

### ---------------------- GRAPH CONSTRUCTION ---------------------- ###
def make_coach_graph(
	crag_graph: Any = None,
	model: Any = None,
	state_schema: type[CoachGraphState] = CoachGraphState,
):
	"""Build and compile the coach graph."""
	coach_model = model or _get_default_coach_model()

	coach_flow = StateGraph(state_schema)
	coach_flow.add_node("prepare_context", node_prepare_coach_context)
	coach_flow.add_node("route_crag_queries", node_route_crag_queries)
	coach_flow.add_node("call_crag", make_call_crag_node(crag_graph))
	coach_flow.add_node("generate_coach_advice", make_generate_coach_advice_node(coach_model))
	coach_flow.add_node("repair_coach_advice", make_repair_coach_advice_node(coach_model))
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
	def coach_node(state: ParentNegotiationState) -> dict:
		original_event_count = len(state.get("event_log", []))
		result = coach_graph.invoke(state)
		updates = {"coach_advice": result.get("coach_advice", {})}
		if result.get("event_log"):
			updates["event_log"] = result["event_log"][original_event_count:]
		return updates

	return coach_node


def invoke_coach_advice(coach_graph: Any, state: ParentNegotiationState) -> CoachAdvice:
	"""Invoke the coach graph and return only the generated advice."""
	result = coach_graph.invoke(state)
	return result.get("coach_advice", {})

