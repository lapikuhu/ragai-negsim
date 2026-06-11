from typing import Any

from app.airag.chains.agents.intent_classifier.intent_classifier_helpers import (
    coerce_intent_classification,
    fallback_intent_classification,
    is_terminal_acceptance_message,
    latest_user_message,
    render_intent_prompt,
)
from app.airag.chains.agents.intent_classifier.intent_classifier_model import (
    IntentClassificationModel,
    IntentClassifierGraphState,
)


def make_classify_intent_node(model: Any):
    """
    Create the generation node for classifying end intent.
    Args:
        model: The language model to use for intent classification, 
            which should support structured output with IntentClassificationModel.
    Returns:
        A function that takes the current graph state and returns a dictionary
        containing the intent classification result, any validation errors, and
        an event log."""

    def node_classify_intent(state: IntentClassifierGraphState) -> dict:
        prompt = render_intent_prompt(state)
        if model is None:
            return {
                "intent_prompt": prompt,
                "intent_validation_error": "Intent classifier model is not configured.",
                "event_log": ["intent_classifier:generation_failed"],
            }

        try:
            result = model.with_structured_output(IntentClassificationModel).invoke(
                prompt
            )
            classification = coerce_intent_classification(result)
            user_message = latest_user_message(state)
            if (
                classification.get("intent") != "end"
                and is_terminal_acceptance_message(user_message)
            ):
                classification = {
                    "intent": "end",
                    "confidence": "high",
                    "reasoning": (
                        "The student explicitly accepted the deal, so the "
                        "simulation should end immediately."
                    ),
                }
        except Exception as exc:
            return {
                "intent_prompt": prompt,
                "intent_validation_error": str(exc),
                "event_log": ["intent_classifier:generation_failed"],
            }

        return {
            "intent_prompt": prompt,
            "intent_classification": classification,
            "intent_validation_error": "",
            "event_log": [
                "intent_classifier:classified "
                f"intent={classification['intent']} "
                f"confidence={classification['confidence']}"
            ],
        }

    return node_classify_intent


def node_finalize_intent(state: IntentClassifierGraphState) -> dict:
    """
    Ensure the graph always yields a safe classifier result.
    Args:
        state: The current state of the intent classifier graph, which 
            may or may not include a valid "intent_classification" entry.
    Returns:         
        A dictionary containing either the valid intent classification from the
         state or a fallback classification if validation failed or was 
         unavailable.
    """
    classification = state.get("intent_classification")
    if classification:
        return {"intent_classification": classification}
    return {
        "intent_classification": fallback_intent_classification(),
        "event_log": ["intent_classifier:fallback_continue"],
    }
