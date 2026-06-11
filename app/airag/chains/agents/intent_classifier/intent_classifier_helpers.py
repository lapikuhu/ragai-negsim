import re
from typing import Any

from app.airag.chains.agents.intent_classifier.intent_classifier_model import (
    IntentClassificationModel,
    IntentClassifierGraphState,
)
from app.airag.prompts.neg_prompts.md_loader import INTENT_CLASSIFIER_PROMPT


TERMINAL_ACCEPTANCE_PATTERNS = (
    r"\bi agree\b",
    r"\bi accept\b",
    r"\bthat works for me\b",
    r"\blet'?s do it\b",
    r"\bwe have a deal\b",
    r"\bit'?s a deal\b",
    r"\bdeal\b",
)


def latest_user_message(state: IntentClassifierGraphState) -> str:
    """
    Return the latest user-authored message content.
    Args:
        state: The current state of the intent classifier graph, which 
            includes a list of messages.
    Returns:
        The content of the most recent message authored by the user, or 
        an empty string if none found.
    """
    for message in reversed(state.get("messages", [])):
        if isinstance(message, dict):
            if message.get("role") in {"user", "human"}:
                return str(message.get("content", ""))
        if getattr(message, "type", None) in {"user", "human"}:
            return str(getattr(message, "content", ""))
    return ""


def render_intent_prompt(state: IntentClassifierGraphState) -> str:
    """
    Render the intent-classifier prompt.
    Args:
        state: The current state of the intent classifier graph.
    Returns:
        The rendered intent-classifier prompt with the latest user message.
    """
    return INTENT_CLASSIFIER_PROMPT.replace(
        "{latest_user_message}",
        latest_user_message(state),
    )


def is_terminal_acceptance_message(message: str) -> bool:
    """
    Detect explicit agreement language that should end the simulation.
    Args:
        message: The latest user-authored message content.
    Returns:
        True when the message contains a clear acceptance phrase.
    """
    normalized = message.strip().lower()
    if not normalized:
        return False
    return any(re.search(pattern, normalized) for pattern in TERMINAL_ACCEPTANCE_PATTERNS)


def coerce_intent_classification(result: Any) -> dict[str, Any]:
    """
    Coerce a model result into the validated classifier payload.
    Args:
        result: The result from the model, which can be an instance of
            IntentClassificationModel, a dictionary, or a JSON string.
    Returns:
        A dictionary representing the validated classifier payload.
    """
    if isinstance(result, IntentClassificationModel):
        return result.model_dump()
    if isinstance(result, dict):
        return IntentClassificationModel.model_validate(result).model_dump()
    return IntentClassificationModel.model_validate_json(str(result)).model_dump()


def fallback_intent_classification() -> dict[str, str]:
    """
    Default to continuing when classification fails or is unavailable.
    Args:
        None
    Returns:
        A dictionary representing the fallback intent classification.
    """
    return {
        "intent": "continue",
        "confidence": "low",
        "reasoning": "Intent classification failed; continue safely.",
    }


def get_default_intent_classifier_model() -> Any | None:
    """
    Best-effort default model loader for the intent classifier.
    Args:
        None
    Returns:
        An instance of the default intent classification model, or None if
        loading fails.
    """
    try:
        from app.airag.llm_models.llm_models import get_openai_llm

        return get_openai_llm("gpt-4o", temperature=0.0)
    except Exception:
        return None
