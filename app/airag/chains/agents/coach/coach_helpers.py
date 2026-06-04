from typing import Any

# local imports
from app.airag.chains.agents.helpers import json_dumps, format_messages
from app.airag.prompts.neg_prompts.md_loader import COACH_PROMPT
from app.airag.chains.agents.coach.coach_model import CoachGraphState
from app.airag.chains.negotiation.negotiation_model import (
	CoachAdvice,
	SideProfile,
)
### -------------------- COACH SPECIFIC HELPERS -------------------- ###

def render_coach_prompt(
	state: CoachGraphState,
	prompt_template: str | None = None,
) -> str:
	"""Render the coach prompt by replacing placeholders with current state values.
	Args:
        state: The current state of the coach graph, containing all relevant information about the negotiation.
    Returns:
        A string containing the rendered coach prompt ready to be sent to the LLM.
	"""
	replacements = {
		"{user_side}": state.get("user_side", ""),
		"{side_a_profile}": json_dumps(state.get("side_a", {})),
		"{side_b_profile}": json_dumps(state.get("side_b", {})),
		"{phase}": state.get("phase", ""),
		"{active_side}": state.get("active_side", ""),
		"{messages}": format_messages(state.get("messages", [])),
		"{current_offer}": json_dumps(state.get("current_offer", {})),
		"{offer_history}": json_dumps(state.get("offer_history", [])),
		"{retrieval_context}": state.get("retrieval_context", ""),
		"{evaluation}": json_dumps(state.get("evaluation", {})),
	}

	prompt = prompt_template or COACH_PROMPT
	for placeholder, value in replacements.items():
		prompt = prompt.replace(placeholder, str(value))
	return prompt


def get_user_profile(state: CoachGraphState) -> SideProfile:
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


def get_existing_retrieval_context(state: CoachGraphState) -> str:
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


def collect_missing_information(state: CoachGraphState) -> list[str]:
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
	user_profile = get_user_profile(state)

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


def build_crag_query(state: CoachGraphState) -> str:
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
	user_profile = get_user_profile(state)
	query_parts = [
		"Provide concise negotiation theory and tactics for coaching a user.",
		f"The user controls {user_side}. The negotiation phase is {phase}.",
	]

	if not current_offer:
		query_parts.append(
			"Focus on clarifying missing offer information and asking useful questions."
		)
	else:
		query_parts.append(f"Current offer: {json_dumps(current_offer)}")

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
		query_parts.append(f"Known risks to address: {json_dumps(detected_risks)}")

	return "\n".join(query_parts)


def fallback_advice(state: CoachGraphState, reason: str) -> CoachAdvice:
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

	missing_information = collect_missing_information(state)
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


def get_default_coach_model() -> Any | None:
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
