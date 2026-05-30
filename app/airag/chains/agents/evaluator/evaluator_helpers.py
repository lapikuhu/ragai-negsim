
# local imports
from app.airag.chains.agents.evaluator.evaluator_model import (
    EvaluatorResponseModel,
    Evaluation,
    EvaluatorGraphState
)
from app.airag.prompts.neg_prompts.md_loader import EVALUATOR_PROMPT
from app.airag.chains.agents.helpers import json_dumps, format_messages
from app.airag.chains.negotiation.negotiation_model import (
	Side, 
	SideProfile,
)

def get_counterpart_side(state: EvaluatorGraphState) -> Side:
	"""Infer counterpart side as opposite the user-controlled side."""
	return "side_a" if state.get("user_side") == "side_b" else "side_b"


def get_side_profile(state: EvaluatorGraphState, side: Side) -> SideProfile:
	"""Return a side profile from graph state."""
	return state.get(side, {})


def get_latest_counterpart_response(state: EvaluatorGraphState) -> str:
	"""Return the latest counterpart response text from parent state fields."""
	counterpart_side = get_counterpart_side(state)
	if counterpart_side == "side_a":
		return state.get("side_a_response", "")
	return state.get("side_b_response", "")


def get_existing_retrieval_context(state: EvaluatorGraphState) -> str:
	retrieval_result = state.get("retrieval_result", {})
	return retrieval_result.get("summary", "") if isinstance(retrieval_result, dict) else ""


def collect_missing_information(state: EvaluatorGraphState) -> list[str]:
	"""Collect state gaps that may weaken evaluation quality."""
	missing = []
	if not state.get("user_side"):
		missing.append("user_side")
	if not state.get("side_a"):
		missing.append("side_a_profile")
	if not state.get("side_b"):
		missing.append("side_b_profile")
	if not state.get("messages"):
		missing.append("messages")
	if not state.get("current_offer"):
		missing.append("current_offer")
	if not state.get("offer_history"):
		missing.append("offer_history")

	for side in ("side_a", "side_b"):
		profile = get_side_profile(state, side)
		for field_name in ("target_value", "reservation_value", "value_preference"):
			if field_name not in profile:
				missing.append(f"{side}.{field_name}")

	return missing


def build_evaluator_crag_query(state: EvaluatorGraphState) -> str:
	"""Build a concise grounding query for negotiation evaluation theory."""
	query_parts = [
		"Provide concise negotiation evaluation theory for assessing the current state.",
		f"Phase: {state.get('phase', 'unknown')}.",
		"Address reservation values, target values, ZOPA, hard constraints, deal quality, concession risk, and next graph action.",
	]

	current_offer = state.get("current_offer", {})
	if current_offer:
		query_parts.append(f"Current offer: {json_dumps(current_offer)}")
	else:
		query_parts.append("Current offer is missing; include how to evaluate with incomplete offer information.")

	offer_history = state.get("offer_history", [])
	if len(offer_history) > 1:
		query_parts.append(
			"Offer history has multiple rounds; include concession trends, anchoring, momentum, and deadlock signals."
		)

	coach_advice = state.get("coach_advice", {})
	if coach_advice:
		query_parts.append(f"Latest coach advice: {json_dumps(coach_advice)}")

	prior_evaluation = state.get("evaluation", {})
	if isinstance(prior_evaluation, dict) and prior_evaluation.get("detected_risks"):
		query_parts.append(f"Previously detected risks: {json_dumps(prior_evaluation.get('detected_risks'))}")

	return "\n".join(query_parts)


def render_evaluator_prompt(state: EvaluatorGraphState) -> str:
	"""Render evaluator_prompt.md with the current graph state."""
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
		"{coach_advice}": json_dumps(state.get("coach_advice", {})),
		"{counterpart_response}": get_latest_counterpart_response(state),
	}

	prompt = EVALUATOR_PROMPT
	for placeholder, value in replacements.items():
		prompt = prompt.replace(placeholder, str(value))
	return prompt


def coerce_evaluator_response(result: Any) -> dict[str, Any]:
	if isinstance(result, EvaluatorResponseModel):
		return result.model_dump()
	if isinstance(result, dict):
		return EvaluatorResponseModel.model_validate(result).model_dump()
	return EvaluatorResponseModel.model_validate_json(str(result)).model_dump()


def map_evaluator_next_action(
	state: EvaluatorGraphState,
	next_best_action: str,
) -> NextAction:
	"""Map evaluator prompt action values to existing ParentNegotiationState values."""
	if next_best_action == "call_counterpart":
		return "call_side_a" if get_counterpart_side(state) == "side_a" else "call_side_b"
	if next_best_action in {"call_coach", "call_retriever", "ask_user", "end"}:
		return next_best_action
	return "ask_user"


def compact_evaluation_from_response(
	state: EvaluatorGraphState,
	response: dict[str, Any],
) -> Evaluation:
	"""Convert full evaluator response to the compact parent Evaluation shape."""
	return {
		"evaluated_side": state.get("user_side", "side_a"),
		"score": response.get("score", 0.5),
		"reasoning": response.get("reasoning", ""),
		"detected_risks": response.get("detected_risks", []),
		"next_best_action": map_evaluator_next_action(
			state,
			response.get("next_best_action", "ask_user"),
		),
	}


def fallback_evaluator_response(
	state: EvaluatorGraphState,
	reason: str,
) -> dict[str, Any]:
	"""Build a valid low-confidence evaluator response for failure paths."""
	missing_information = [*state.get("missing_information", [])]
	if reason:
		missing_information.append(f"evaluator_generation_error: {reason}")

	grounding_note = (
		"I could not base this evaluation on retrieved documents. I will rely on the available "
		"session state and general negotiation training to provide a low-confidence evaluation anyway."
	)

	return EvaluatorResponseModel(
		score=0.5,
		phase_assessment=grounding_note,
		side_a_assessment={
			"position": "unknown from available information",
			"target_value_check": "unknown",
			"reservation_value_check": "unknown",
			"constraint_check": "unknown",
			"risk_level": "medium",
		},
		side_b_assessment={
			"position": "unknown from available information",
			"target_value_check": "unknown",
			"reservation_value_check": "unknown",
			"constraint_check": "unknown",
			"risk_level": "medium",
		},
		zopa_assessment={
			"zopa_exists": None,
			"reasoning": "ZOPA cannot be determined reliably from the available information.",
			"confidence": "low",
		},
		detected_risks=["Evaluation confidence is low because grounding or structured output validation failed."],
		deal_quality={
			"for_side_a": "unknown",
			"for_side_b": "unknown",
			"overall": "unknown",
		},
		next_best_action="ask_user",
		reasoning=grounding_note,
		missing_information=missing_information,
		confidence="low",
	).model_dump()


def get_default_evaluator_model() -> Any | None:
	"""Lazily construct a default model so imports remain cheap and testable."""
	try:
		from app.airag.llm_models.llm_models import get_openai_llm

		return get_openai_llm("gpt-4o", temperature=0.0)
	except Exception:
		try:
			from langchain_openai import ChatOpenAI

			return ChatOpenAI(model="gpt-4o", temperature=0.0)
		except Exception:
			return None
