from typing import Any
from langchain_core.messages import BaseMessage

from app.airag.chains.agents.evaluator.evaluator_model import (
    Evaluation,
    EvaluatorGraphState,
    EvaluatorResponseModel,
    FinalEvaluatorResponseModel,
)
from app.airag.chains.agents.helpers import (
	append_missing_context_sections,
	append_custom_prompt_extension,
	flatten_message_metadata,
	format_messages,
	json_dumps,
	render_prompt_template,
)
from app.airag.chains.crag.helpers import format_trusted_context_sections
from app.airag.chains.negotiation.negotiation_model import (
	FinalEvaluation,
	Side,
	SideProfile,
)
from app.airag.prompts.neg_prompts.md_loader import (
    EVALUATOR_FINAL_MODE_PROMPT,
    EVALUATOR_PROMPT,
)


PROXY_EVALUATION_GUIDANCE = [
	"Proxy authorship rules:",
	'- If `metadata.user_reply_origin == "auto_user_proxy"`, treat that user-role message as proxy-authored.',
	'- If `metadata.user_reply_origin == "user"`, treat that message as student-authored.',
	"- Missing provenance means the message should be treated as student-authored.",
	"- Distinguish student-authored tactics from proxy-authored tactics in your analysis.",
	"- Do not count proxy-authored tactics as evidence of the student's own negotiation skill.",
	"- Evaluate the proxy's tactics when present and explain their effect on the negotiation.",
	"- A small amount of proxy use is a limited negative signal for the student; sustained proxy reliance is a serious negative signal.",
]


def _message_metadata(message: Any) -> dict[str, Any]:
	"""
	Extract metadata from supported message shapes.
	Args:
		message: The message object from which to extract metadata.
	Returns:
		A dictionary containing the extracted metadata.
	"""
	if isinstance(message, dict):
		return flatten_message_metadata(message.get("metadata"))
	if isinstance(message, BaseMessage):
		return flatten_message_metadata(message.additional_kwargs)
	return {}


def summarize_proxy_authorship(messages: list[Any] | None) -> dict[str, Any]:
	"""
	Summarize student-vs-proxy authorship from the transcript.
	Args:
		messages: The list of messages in the negotiation transcript.
	Returns:
		A dictionary summarizing the student-vs-proxy authorship.
	"""
	student_authored_turns = 0
	proxy_authored_turns = 0

	for message in messages or []:
		if isinstance(message, dict):
			role = message.get("role") or message.get("type")
		elif isinstance(message, BaseMessage):
			role = message.type
		else:
			role = getattr(message, "role", None) or getattr(message, "type", None)

		if role not in {"user", "human"}:
			continue

		origin = _message_metadata(message).get("user_reply_origin", "user")
		if origin == "auto_user_proxy":
			proxy_authored_turns += 1
		else:
			student_authored_turns += 1

	if proxy_authored_turns == 0:
		proxy_extent = "none"
		impact_on_student_score = "No proxy use detected."
	elif student_authored_turns == 0:
		proxy_extent = "extensive"
		impact_on_student_score = (
			"All student-side turns were proxy-authored, so student skill should be scored at 0.0."
		)
	elif proxy_authored_turns == 1:
		proxy_extent = "limited"
		impact_on_student_score = (
			"Limited proxy use should slightly reduce confidence in the student's score."
		)
	else:
		proxy_extent = "extensive"
		impact_on_student_score = (
			"Sustained proxy use should materially reduce the student's score and be treated as a serious negative signal."
		)

	return {
		"student_authored_turns": student_authored_turns,
		"proxy_authored_turns": proxy_authored_turns,
		"proxy_extent": proxy_extent,
		"impact_on_student_score": impact_on_student_score,
	}


def append_proxy_guidance(prompt: str, template: str, messages: list[Any] | None) -> str:
	"""
	Append proxy guidance additively, even for custom templates.
	Args:
		prompt: The current prompt string.
		template: The original prompt template string.
		messages: The list of messages in the negotiation transcript.
	Returns:
		The prompt string with proxy guidance appended if not already present."""
	additions = []
	if "Proxy authorship rules:" not in template:
		additions.extend(PROXY_EVALUATION_GUIDANCE)
	additions.extend(
		[
			"Proxy authorship summary:",
			json_dumps(summarize_proxy_authorship(messages)),
		]
	)
	return "\n".join([prompt, "", *additions]) if additions else prompt

# Helper candidate
def get_counterpart_side(state: EvaluatorGraphState) -> Side:
	"""
	Infer counterpart side as opposite the user-controlled side.
	Args:
		state: The current evaluator graph state containing negotiation 
			context.
	Returns:
		The side opposite to the user-controlled side.
	"""
	return "side_a" if state.get("user_side") == "side_b" else "side_b"


def get_side_profile(state: EvaluatorGraphState, side: Side) -> SideProfile:
	"""
	Return a side profile from graph state.
	Args:
		state: The current evaluator graph state containing negotiation 
			context.
		side: The side for which to retrieve the profile.
	Returns:
		The profile of the specified side.
	"""
	return state.get(side, {})


def get_latest_counterpart_response(state: EvaluatorGraphState) -> str:
	"""
	Return the latest counterpart response text from parent state fields.
	Args:
		state: The current evaluator graph state containing negotiation 
			context.
	Returns:
		The latest counterpart response text.
	"""
	counterpart_side = get_counterpart_side(state)
	if counterpart_side == "side_a":
		return state.get("side_a_response", "")
	return state.get("side_b_response", "")


def get_existing_retrieval_context(state: EvaluatorGraphState) -> str:
	"""
	Return the existing retrieval context from the evaluator graph state.
	Args:
		state: The current evaluator graph state containing negotiation 
			context.
	Returns:
		The existing retrieval context summary.
	"""
	retrieval_result = state.get("retrieval_result", {})
	return retrieval_result.get("summary", "") if isinstance(retrieval_result, dict) else ""


def collect_missing_information(state: EvaluatorGraphState) -> list[str]:
	"""
	Collect state gaps that may weaken evaluation quality.
	Args:
		state: The current evaluator graph state containing negotiation 
			context.
	Returns:
		A list of missing information keys.
	"""
	missing = []
	if not state.get("user_side"):
		missing.append("user_side")
	if not state.get("side_a"):
		missing.append("side_a_profile")
	if not state.get("side_b"):
		missing.append("side_b_profile")
	if not state.get("scenario_public_context"):
		missing.append("scenario_public_context")
	if not state.get("side_a_private_context"):
		missing.append("side_a_private_context")
	if not state.get("side_b_private_context"):
		missing.append("side_b_private_context")
	if not state.get("messages"):
		missing.append("messages")
	if not state.get("current_offer"):
		missing.append("current_offer")
	if not state.get("offer_history"):
		missing.append("offer_history")
	return missing

# Check prompts quality
def build_evaluator_rag_query(state: EvaluatorGraphState) -> str:
	"""
	Build a concise grounding query for negotiation evaluation theory.
	Args:
		state: The current evaluator graph state containing negotiation 
			context.
	Returns:
		A string representing the grounding query for evaluation.
	"""
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


def build_evaluator_trusted_context(state: EvaluatorGraphState) -> str:
	"""
	Build the evaluator-authorized trusted simulation evidence passed into CRAG.
	Args:
		state: The current evaluator graph state.
	Returns:
		A labeled plain-text summary of trusted simulation state.
	"""
	return format_trusted_context_sections(
		[
			("User side", state.get("user_side", "")),
			("Negotiation phase", state.get("phase", "")),
			("Evaluation mode", state.get("evaluation_mode", "")),
			("Public scenario context", state.get("scenario_public_context", {})),
			("Side A profile", state.get("side_a", {})),
			("Side B profile", state.get("side_b", {})),
			("Side A private context", state.get("side_a_private_context", {})),
			("Side B private context", state.get("side_b_private_context", {})),
			("Current offer", state.get("current_offer", {})),
			("Offer history", state.get("offer_history", [])),
		]
	)


def render_evaluator_prompt(
	state: EvaluatorGraphState,
	prompt_template: str | None = None,
) -> str:
	"""
	Render evaluator_prompt.md with the current graph state.
	Args:
		state: The current evaluator graph state containing negotiation 
			context.
		prompt_template: Optional custom prompt extension template for the evaluator.
	Returns:
		A string representing the rendered evaluator prompt.
	"""
	replacements = {
		"{user_side}": state.get("user_side", ""),
		"{side_a_profile}": json_dumps(state.get("side_a", {})),
		"{side_b_profile}": json_dumps(state.get("side_b", {})),
		"{public_context}": json_dumps(state.get("scenario_public_context", {})),
		"{side_a_private_context}": json_dumps(state.get("side_a_private_context", {})),
		"{side_b_private_context}": json_dumps(state.get("side_b_private_context", {})),
		"{phase}": state.get("phase", ""),
		"{active_side}": state.get("active_side", ""),
		"{messages}": format_messages(state.get("messages", [])),
		"{current_offer}": json_dumps(state.get("current_offer", {})),
		"{offer_history}": json_dumps(state.get("offer_history", [])),
		"{retrieval_context}": state.get("retrieval_context", ""),
		"{coach_advice}": json_dumps(state.get("coach_advice", {})),
		"{counterpart_response}": get_latest_counterpart_response(state),
	}

	template = EVALUATOR_PROMPT
	prompt = render_prompt_template(template, replacements)
	prompt = append_missing_context_sections(
		prompt,
		template,
		[
			("{public_context}", "PUBLIC CONTEXT", state.get("scenario_public_context", {})),
			(
				"{side_a_private_context}",
				"SIDE A PRIVATE CONTEXT",
				state.get("side_a_private_context", {}),
			),
			(
				"{side_b_private_context}",
				"SIDE B PRIVATE CONTEXT",
				state.get("side_b_private_context", {}),
			),
		],
	)
	prompt = append_custom_prompt_extension(prompt, prompt_template, replacements)
	return append_proxy_guidance(prompt, template, state.get("messages", []))


def render_final_evaluator_prompt(
	state: EvaluatorGraphState,
	prompt_template: str | None = None,
) -> str:
	"""
	Render the final evaluator prompt using the full transcript.
	Args:
		state: The current evaluator graph state containing negotiation 
			context.
		prompt_template: Optional custom prompt extension template for the final
			evaluator.
	Returns:
		A string representing the rendered final evaluator prompt.
	"""
	replacements = {
		"{user_side}": state.get("user_side", ""),
		"{side_a_profile}": json_dumps(state.get("side_a", {})),
		"{side_b_profile}": json_dumps(state.get("side_b", {})),
		"{public_context}": json_dumps(state.get("scenario_public_context", {})),
		"{side_a_private_context}": json_dumps(state.get("side_a_private_context", {})),
		"{side_b_private_context}": json_dumps(state.get("side_b_private_context", {})),
		"{phase}": state.get("phase", ""),
		"{messages}": format_messages(state.get("messages", [])),
		"{current_offer}": json_dumps(state.get("current_offer", {})),
		"{offer_history}": json_dumps(state.get("offer_history", [])),
		"{rolling_evaluation}": json_dumps(state.get("evaluation", {})),
		"{coach_advice}": json_dumps(state.get("coach_advice", {})),
		"{retrieval_context}": state.get("retrieval_context", ""),
	}

	template = EVALUATOR_FINAL_MODE_PROMPT
	prompt = render_prompt_template(template, replacements)
	prompt = append_missing_context_sections(
		prompt,
		template,
		[
			("{public_context}", "PUBLIC CONTEXT", state.get("scenario_public_context", {})),
			(
				"{side_a_private_context}",
				"SIDE A PRIVATE CONTEXT",
				state.get("side_a_private_context", {}),
			),
			(
				"{side_b_private_context}",
				"SIDE B PRIVATE CONTEXT",
				state.get("side_b_private_context", {}),
			),
			(
				"{rolling_evaluation}",
				"ROLLING EVALUATION",
				state.get("evaluation", {}),
			),
		],
	)
	prompt = append_custom_prompt_extension(prompt, prompt_template, replacements)
	prompt = append_proxy_guidance(prompt, template, state.get("messages", []))
	if 'If every student-side turn was proxy-authored, set "overall_score" to 0.0.' not in template:
		prompt = "\n".join(
			[
				prompt,
				"",
				'If every student-side turn was proxy-authored, set "overall_score" to 0.0.',
				"You should still evaluate the proxy's tactics and their effect on the negotiation in the narrative fields.",
			]
		)
	return prompt


def coerce_evaluator_response(result: Any, final_mode: bool = False) -> dict[str, Any]:
	"""
	Coerce an evaluator response into a validated dictionary format.
	Args:
		result: The evaluator response to be coerced.
		final_mode: Whether to use the final evaluator response model.
	Returns:
		A dictionary representing the validated evaluator response.
	"""
	model_cls = FinalEvaluatorResponseModel if final_mode else EvaluatorResponseModel
	if isinstance(result, model_cls):
		return result.model_dump()
	if isinstance(result, dict):
		return model_cls.model_validate(result).model_dump()
	return model_cls.model_validate_json(str(result)).model_dump()


def compact_evaluation_from_response(
	state: EvaluatorGraphState,
	response: dict[str, Any],
) -> Evaluation:
	"""
	Convert full evaluator response to the compact parent Evaluation shape.
	Args:
		state: The current evaluator graph state containing negotiation 
			context.
		response: The full evaluator response to be converted.
	Returns:
		A dictionary representing the compact evaluation.
	"""
	proxy_usage_assessment = summarize_proxy_authorship(state.get("messages", []))
	return {
		"evaluated_side": state.get("user_side", "side_a"),
		"score": response.get("score", 0.5),
		"reasoning": response.get("reasoning", ""),
		"detected_risks": response.get("detected_risks", []),
		"proxy_usage_assessment": proxy_usage_assessment,
		"next_best_action": response.get("next_best_action", "continue"),
		"confidence": response.get("confidence", "low"),
		"missing_information": response.get("missing_information", []),
	}


def final_evaluation_from_response(
	state: EvaluatorGraphState,
	response: dict[str, Any],
) -> FinalEvaluation:
	"""Convert final evaluator output to the parent final-evaluation shape."""
	proxy_usage_assessment = summarize_proxy_authorship(state.get("messages", []))
	overall_score = response.get("overall_score", 0.5)
	if (
		proxy_usage_assessment["student_authored_turns"] == 0
		and proxy_usage_assessment["proxy_authored_turns"] > 0
	):
		overall_score = 0.0
	return {
		"evaluated_side": state.get("user_side", "side_a"),
		"overall_score": overall_score,
		"goal_achievement": response.get("goal_achievement", ""),
		"strengths": response.get("strengths", []),
		"mistakes": response.get("mistakes", []),
		"concession_quality": response.get("concession_quality", ""),
		"communication_quality": response.get("communication_quality", ""),
		"outcome_quality": response.get("outcome_quality", ""),
		"proxy_usage_assessment": proxy_usage_assessment,
		"lessons": response.get("lessons", []),
		"reasoning": response.get("reasoning", ""),
		"confidence": response.get("confidence", "low"),
		"missing_information": response.get("missing_information", []),
	}

# The response here is fine
def fallback_evaluator_response(
	state: EvaluatorGraphState,
	reason: str,
) -> dict[str, Any]:
	"""
	Build a valid low-confidence evaluator response for failure paths.
	Args:
		state: The current evaluator graph state containing negotiation 
			context.
		reason: The reason for the fallback response.
	Returns:
		A dictionary representing the low-confidence evaluator response.
	"""
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
		proxy_usage_assessment=summarize_proxy_authorship(state.get("messages", [])),
		next_best_action="continue",
		reasoning=grounding_note,
		missing_information=missing_information,
		confidence="low",
	).model_dump()


def fallback_final_evaluator_response(
	state: EvaluatorGraphState,
	reason: str,
) -> dict[str, Any]:
	"""
	Build a safe final assessment when final evaluation fails.
	Args:
		state: The current evaluator graph state containing negotiation 
			context.
		reason: The reason for the fallback response.
	Returns:
		A dictionary representing the low-confidence final evaluator response.
	"""
	missing_information = [*state.get("missing_information", [])]
	if reason:
		missing_information.append(f"final_evaluator_generation_error: {reason}")

	return FinalEvaluatorResponseModel(
		overall_score=0.5,
		goal_achievement="Overall goal achievement is uncertain from the available information.",
		strengths=["A reliable final assessment could not be generated."],
		mistakes=["The final evaluator fell back to a low-confidence summary."],
		concession_quality="unknown",
		communication_quality="unknown",
		outcome_quality="unknown",
		proxy_usage_assessment=summarize_proxy_authorship(state.get("messages", [])),
		lessons=["Review the transcript manually before drawing strong conclusions."],
		reasoning=(
			"I could not generate a grounded final evaluation, so this is a "
			"low-confidence fallback summary."
		),
		confidence="low",
		missing_information=missing_information,
	).model_dump()

# Helper candidate for all agents/graphs
def get_default_evaluator_model() -> Any | None:
	"""
	Best-effort default model loader for evaluator generation.
	Returns:
		An instance of the default model for evaluator response generation, 
		or None if no model is available.
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
