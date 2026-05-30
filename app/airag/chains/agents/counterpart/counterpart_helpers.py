from typing import Any
#local imports
from app.airag.chains.agents.helpers import json_dumps, format_messages
from app.airag.chains.negotiation.negotiation_model import (
    Side,
    SideProfile
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


def get_side_profile(state: CounterpartGraphState, side: Side) -> SideProfile:
	"""Return a side profile from graph state."""
	return state.get(side, {})


def get_counterpart_profile(state: CounterpartGraphState) -> SideProfile:
	"""Return the inferred counterpart profile."""
	return get_side_profile(state, get_counterpart_side(state))


def collect_missing_information(state: CounterpartGraphState) -> list[str]:
	"""Collect state gaps that may weaken counterpart response generation."""
	missing = []
	counterpart_profile = get_counterpart_profile(state)

	if not state.get("user_side"):
		missing.append("user_side")
	if not state.get("side_a"):
		missing.append("side_a_profile")
	if not state.get("side_b"):
		missing.append("side_b_profile")
	if not state.get("current_offer"):
		missing.append("current_offer")
	if not state.get("offer_history"):
		missing.append("offer_history")

	for field_name in ("target_value", "reservation_value", "value_preference"):
		if field_name not in counterpart_profile:
			missing.append(f"counterpart_profile.{field_name}")

	return missing


def render_counterpart_prompt(state: CounterpartGraphState) -> str:
	"""Render counterpart_prompt.md with the current graph state."""
	replacements = {
		"{user_side}": state.get("user_side", ""),
		"{counterpart_side}": state.get("counterpart_side", get_counterpart_side(state)),
		"{side_a_profile}": json_dumps(state.get("side_a", {})),
		"{side_b_profile}": json_dumps(state.get("side_b", {})),
		"{phase}": state.get("phase", ""),
		"{active_side}": state.get("active_side", ""),
		"{messages}": format_messages(state.get("messages", [])),
		"{current_offer}": json_dumps(state.get("current_offer", {})),
		"{offer_history}": json_dumps(state.get("offer_history", [])),
		"{retrieval_context}": get_retrieval_context(state),
		"{evaluation}": json_dumps(state.get("evaluation", {})),
	}

	prompt = COUNTERPART_PROMPT
	for placeholder, value in replacements.items():
		prompt = prompt.replace(placeholder, str(value))
	return prompt


def get_retrieval_context(state: CounterpartGraphState) -> str:
	retrieval_result = state.get("retrieval_result", {})
	return retrieval_result.get("summary", "") if isinstance(retrieval_result, dict) else ""


def coerce_counterpart_response(result: Any) -> dict[str, Any]:
	if isinstance(result, CounterpartResponseModel):
		return result.model_dump()
	if isinstance(result, dict):
		return CounterpartResponseModel.model_validate(result).model_dump()
	return CounterpartResponseModel.model_validate_json(str(result)).model_dump()


def fallback_counterpart_response(
	state: CounterpartGraphState,
	reason: str,
) -> dict[str, Any]:
	counterpart_side = state.get("counterpart_side", get_counterpart_side(state))
	message = (
		"Before I can respond constructively, I need a bit more clarity on the "
		"current offer and the specific terms you want me to consider."
	)
	missing_information = state.get("missing_information", []) or collect_missing_information(state)
	risk: RiskLevel = "high" if missing_information else "medium"

	return CounterpartResponseModel(
		side=counterpart_side,
		message=message,
		action="clarify",
		offer={
			"side": counterpart_side,
			"price": None,
			"terms": {},
			"raw_text": message,
		},
		private_notes={
			"strategy_used": "fallback_clarification",
			"reservation_value_check": "unknown",
			"target_value_check": "unknown",
			"risk": risk,
		},
	).model_dump()


def get_default_counterpart_model() -> Any | None:
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
