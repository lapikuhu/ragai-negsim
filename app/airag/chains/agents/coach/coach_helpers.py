from typing import Any

from app.airag.chains.agents.coach.coach_model import CoachGraphState
from app.airag.chains.agents.helpers import (
	append_missing_context_sections,
	append_custom_prompt_extension,
	format_messages,
	json_dumps,
	render_prompt_template,
)
from app.airag.chains.crag.helpers import format_trusted_context_sections
from app.airag.chains.negotiation.negotiation_model import CoachAdvice
from app.airag.prompts.neg_prompts.md_loader import COACH_PROMPT


def render_coach_prompt(
	state: CoachGraphState,
	prompt_template: str | None = None,
) -> str:
	"""
	Render the coach prompt with only coach-safe context.
	Coach-safe context includes information that is either public or 
	explicitly designated as coach-accessible. 
	Args: 
		state: The current state of the coach graph, containing various 
			context fields.
		prompt_template: Optional custom prompt extension template.
	Returns:
	A string containing the rendered prompt ready for coach generation.
	"""
	replacements = {
		"{user_side}": state.get("user_side", ""),
		"{public_context}": json_dumps(state.get("scenario_public_context", {})),
		"{student_private_context}": json_dumps(state.get("student_private_context", {})),
		"{phase}": state.get("phase", ""),
		"{active_side}": state.get("active_side", ""),
		"{messages}": format_messages(state.get("messages", [])),
		"{current_offer}": json_dumps(state.get("current_offer", {})),
		"{offer_history}": json_dumps(state.get("offer_history", [])),
		"{retrieval_context}": state.get("retrieval_context", ""),
	}
	template = COACH_PROMPT
	prompt = render_prompt_template(template, replacements)
	prompt = append_missing_context_sections(
		prompt,
		template,
		[
			("{public_context}", "PUBLIC CONTEXT", state.get("scenario_public_context", {})),
			(
				"{student_private_context}", # Coach has access to student private context
				"STUDENT PRIVATE CONTEXT",
				state.get("student_private_context", {}),
			),
		],
	)
	return append_custom_prompt_extension(prompt, prompt_template, replacements)


def get_student_private_context(state: CoachGraphState) -> dict[str, Any]:
	"""
	Retrieve the student private context from the coach graph state.
	Args:
		state: The current state of the coach graph.
	Returns:
		A dictionary containing the student private context, or an empty 
		dictionary if not available.
	"""
	value = state.get("student_private_context", {})
	return value if isinstance(value, dict) else {}


def collect_missing_information(state: CoachGraphState) -> list[str]:
	"""
	Collect state gaps that may weaken coach advice quality.
	Args:
		state: The current state of the coach graph.
	Returns:
		A list of strings representing the missing information keys.
	"""
	missing = []

	if not state.get("user_side"):
		missing.append("user_side")
	if not state.get("scenario_public_context"):
		missing.append("scenario_public_context")
	if not get_student_private_context(state):
		missing.append("student_private_context")
	if not state.get("current_offer"):
		missing.append("current_offer")
	if not state.get("offer_history"):
		missing.append("offer_history")

	return missing


def build_rag_query(state: CoachGraphState) -> str:
	"""
	Build a coach-local RAG query without evaluator or counterpart secrets.
	Args:
		state: The current state of the coach graph.
	Returns:
		A string containing the RAG query.
	"""
	user_side = state.get("user_side", "the user-controlled side")
	phase = state.get("phase", "unknown")
	current_offer = state.get("current_offer", {})
	offer_history = state.get("offer_history", [])
	student_context = get_student_private_context(state)
	query_parts = [
		"Provide concise negotiation theory and tactics for coaching a user.",
		f"The user controls {user_side}. The negotiation phase is {phase}.",
		f"Public scenario context: {json_dumps(state.get('scenario_public_context', {}))}",
		f"Student private context: {json_dumps(student_context)}",
	]

	if not current_offer:
		query_parts.append(
			"Focus on clarifying missing offer information and asking useful questions."
		)
	else:
		query_parts.append(f"Current offer: {json_dumps(current_offer)}")

	if student_context:
		query_parts.append(
			"Discuss target values, reservation values, BATNA protection, and concession strategy."
		)

	if len(offer_history) > 1:
		query_parts.append(
			"Discuss concession patterns, anchoring, momentum, and avoiding premature concessions."
		)

	return "\n".join(query_parts)


def build_coach_trusted_context(state: CoachGraphState) -> str:
	"""
	Build the coach-safe trusted simulation evidence passed into CRAG.
	Args:
		state: The current coach graph state.
	Returns:
		A labeled plain-text summary of trusted simulation state.
	"""
	return format_trusted_context_sections(
		[
			("User side", state.get("user_side", "")),
			("Negotiation phase", state.get("phase", "")),
			("Public scenario context", state.get("scenario_public_context", {})),
			("Student private context", get_student_private_context(state)),
			("Current offer", state.get("current_offer", {})),
			("Offer history", state.get("offer_history", [])),
		]
	)

# Check and change: fallback can rely the conversation itself and improvise
# after explicitly stating the missing information. Check with the prompt.
def fallback_advice(state: CoachGraphState, reason: str) -> CoachAdvice:
	"""
	Generate low-confidence fallback advice when coach generation fails.
	Args:
		state: The current state of the coach graph.
		reason: The reason for the fallback advice.
	Returns:
		A dictionary containing the fallback coach advice.
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
	Best-effort default LLM for coach generation.
	Args:
		None
	Returns:
		An instance of the default LLM for coach generation, or None if 
		not available.
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
