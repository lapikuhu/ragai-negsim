from typing import Any
#local imports
from app.airag.chains.agents.helpers import (
	append_missing_context_sections,
	append_custom_prompt_extension,
	format_messages,
	json_dumps,
	render_prompt_template,
)
from app.airag.chains.negotiation.negotiation_model import (
    Side,
)
from app.airag.chains.agents.counterpart.counterpart_model import (
    RiskLevel,
    CounterpartResponseModel,
    CounterpartGraphState,
)
from app.airag.prompts.neg_prompts.md_loader import COUNTERPART_PROMPT

def get_counterpart_side(state: CounterpartGraphState) -> Side:
	"""Infer the counterpart as the side opposite the user-controlled side."""
	return "side_a" if state.get("user_side") == "side_b" else "side_b"


def get_counterpart_persona(state: CounterpartGraphState) -> dict[str, Any]:
	"""Return explicit counterpart persona context from graph state."""
	persona = state.get("counterpart_persona", {})
	return persona if isinstance(persona, dict) else {}


def get_own_private_context(state: CounterpartGraphState) -> dict[str, Any]:
	value = state.get("own_private_context", {})
	return value if isinstance(value, dict) else {}


def build_effective_counterpart_profile(state: CounterpartGraphState) -> dict[str, Any]:
	"""Merge persona defaults with counterpart private runtime context."""
	persona = get_counterpart_persona(state)
	counterpart_profile = get_own_private_context(state)
	persona_defaults = {
		"persona_id": persona.get("id"),
		"name": persona.get("name"),
		"description": persona.get("description"),
		"role": persona.get("role"),
		"goal": persona.get("goal"),
		"constraints": persona.get("constraints"),
		"batna": persona.get("batna"),
		"reservation_value": persona.get("reservation_value"),
		"target_value": persona.get("target_value"),
		"value_preference": persona.get("value_preference"),
	}
	return {
		key: value
		for key, value in {**persona_defaults, **counterpart_profile}.items()
		if value is not None
	}


def collect_missing_information(state: CounterpartGraphState) -> list[str]:
	"""Collect state gaps that may weaken counterpart response generation."""
	missing = []

	if not state.get("user_side"):
		missing.append("user_side")
	if not state.get("scenario_public_context"):
		missing.append("scenario_public_context")
	if not state.get("own_private_context"):
		missing.append("own_private_context")
	if not get_counterpart_persona(state):
		missing.append("counterpart_persona")
	if not state.get("current_offer"):
		missing.append("current_offer")
	if not state.get("offer_history"):
		missing.append("offer_history")

	return missing


def render_counterpart_prompt(
	state: CounterpartGraphState,
	prompt_template: str | None = None,
) -> str:
	"""Render counterpart_prompt.md with the current graph state.
	Args:
		state: The current graph state containing negotiation context.
		prompt_template: Optional custom prompt extension template.
	Returns:
		A string with the prompt ready to be sent to the LLM.
	"""
	effective_counterpart_profile = build_effective_counterpart_profile(state)
	replacements = {
		"{user_side}": state.get("user_side", ""),
		"{counterpart_side}": state.get("counterpart_side", get_counterpart_side(state)),
		"{public_context}": json_dumps(state.get("scenario_public_context", {})),
		"{own_private_context}": json_dumps(state.get("own_private_context", {})),
		"{counterpart_persona}": json_dumps(get_counterpart_persona(state)),
		"{effective_counterpart_profile}": json_dumps(effective_counterpart_profile),
		"{phase}": state.get("phase", ""),
		"{active_side}": state.get("active_side", ""),
		"{messages}": format_messages(state.get("messages", [])),
		"{current_offer}": json_dumps(state.get("current_offer", {})),
		"{offer_history}": json_dumps(state.get("offer_history", [])),
	}

	template = COUNTERPART_PROMPT
	prompt = render_prompt_template(template, replacements)
	prompt = append_missing_context_sections(
		prompt,
		template,
		# Build the prompt with the allowed public and private context sections,
		# and the persona.
		# Careful: The master prompt must be aware of these fields.
		[
			("{public_context}", "PUBLIC CONTEXT", state.get("scenario_public_context", {})),
			("{own_private_context}", "YOUR PRIVATE CONTEXT", state.get("own_private_context", {})),
			("{counterpart_persona}", "YOUR PERSONA", get_counterpart_persona(state)),
		],
	)
	return append_custom_prompt_extension(prompt, prompt_template, replacements)


def coerce_counterpart_response(result: Any) -> dict[str, Any]:
	"""
	Coerce a counterpart response into a standardized dictionary format.
	Args:
		result: The counterpart response, which can be a CounterpartResponseModel,
			dictionary, or JSON string.
	Returns:
		A dictionary representation of the counterpart response.
	"""
	if isinstance(result, CounterpartResponseModel):
		return result.model_dump()
	if isinstance(result, dict):
		return CounterpartResponseModel.model_validate(result).model_dump()
	return CounterpartResponseModel.model_validate_json(str(result)).model_dump()

# Check. Fallback only if LLM fails; perhaps change the message to indicate
# the LLM failure?
def fallback_counterpart_response(
	state: CounterpartGraphState,
	reason: str,
) -> dict[str, Any]:
	"""
	Generate a fallback counterpart response when the state is incomplete 
	or unclear.
	Args:
		state: The current graph state containing negotiation context.
		reason: The reason for triggering the fallback response.
	Returns:
		A dictionary representation of the fallback counterpart response.
	"""
	counterpart_side = state.get("counterpart_side", get_counterpart_side(state))
	scenario_context = state.get("scenario_public_context", {})
	scenario_name = (
		scenario_context.get("name")
		if isinstance(scenario_context, dict)
		else None
	)
	if scenario_context:
		scenario_label = scenario_name or "current negotiation"
		message = (
			f"In the {scenario_label} scenario, I cannot agree to the proposal "
			"as stated. I am willing to consider a narrower accommodation or a "
			"concrete trade-off that protects my side's interests."
		)
		action = "counter"
		strategy_used = "scenario_aware_fallback"
	else:
		message = (
			"Before I can respond constructively, I need a bit more clarity on "
			"the current offer and the specific terms you want me to consider."
		)
		action = "clarify"
		strategy_used = "fallback_clarification"
	missing_information = state.get("missing_information", []) or collect_missing_information(state)
	risk: RiskLevel = "high" if missing_information else "medium"

	return CounterpartResponseModel(
		side=counterpart_side,
		message=message,
		action=action,
		offer={
			"side": counterpart_side,
			"price": None,
			"terms": {},
			"raw_text": message,
		},
		private_notes={
			"strategy_used": strategy_used,
			"reservation_value_check": "unknown",
			"target_value_check": "unknown",
			"risk": risk,
		},
	).model_dump()


def get_default_counterpart_model() -> Any | None:
	"""
	Lazily construct a default model so imports remain cheap and testable.
	Args:
		None
	Returns:
		An instance of the default LLM model for counterpart response 
		generation, or None if no suitable model is available.
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
