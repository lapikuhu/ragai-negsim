
###
# This intent classifier node is responsible for classifying the user's intent 
# during the negotiation simulation, if they want to continue or stop.
###

from typing import Any
from langchain_core.runnables.config import RunnableConfig
from langsmith import traceable

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
from app.airag.observability.evidence_ledger import update_agent_ledger
from app.airag.observability.llm_usage import extend_runnable_config, invoke_with_config

def make_classify_intent_node(model: Any):
    """
    Create the generation node for classifying end intent.
    Args:
        model: The language model to use for intent classification, 
            which should support structured output with IntentClassificationModel.
    Returns:
        A function that takes the current graph state and returns a dictionary
        containing the intent classification result, any validation errors, 
        an event log, and the updated evidence ledger.
        """
    @traceable
    def node_classify_intent(
        state: IntentClassifierGraphState,
        config: RunnableConfig | None = None,
    ) -> dict:
        prompt = render_intent_prompt(state)
        if model is None:
            ledger = update_agent_ledger(
                state,
                agent_name="intent_classifier",
                step_name="generate",
                status="failed",
                detail={"reason": "model_not_configured", "prompt_chars": len(prompt)},
            )
            return {
                "intent_prompt": prompt,
                "intent_validation_error": "Intent classifier model is not configured.",
                "event_log": ["intent_classifier:generation_failed"],
                "evidence_ledger": ledger,
            }

        try:
            invoke_config = extend_runnable_config(
                config,
                tags=["agent:intent_classifier", "node:classify", "prompt:intent_classifier"],
                metadata={
                    "agent": "intent_classifier",
                    "node": "classify",
                    "prompt": "intent_classifier",
                },
                run_name="intent_classifier.classify",
            )
            result = invoke_with_config(
                model.with_structured_output(IntentClassificationModel),
                prompt,
                invoke_config,
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
            ledger = update_agent_ledger( # Log the failure in the evidence ledger for observability.
                state,
                agent_name="intent_classifier",
                step_name="generate",
                status="failed",
                detail={"error": str(exc), "prompt_chars": len(prompt)},
            )
            return {
                "intent_prompt": prompt,
                "intent_validation_error": str(exc),
                "event_log": ["intent_classifier:generation_failed"],
                "evidence_ledger": ledger,
            }

        ledger = update_agent_ledger(
            state,
            agent_name="intent_classifier",
            step_name="generate",
            status="success",
            detail={"prompt_chars": len(prompt)},
            output_summary={
                "kind": "intent_classification",
                "intent": classification["intent"],
                "confidence": classification["confidence"],
            },
        )
        return {
            "intent_prompt": prompt,
            "intent_classification": classification,
            "intent_validation_error": "",
            "event_log": [
                "intent_classifier:classified "
                f"intent={classification['intent']} "
                f"confidence={classification['confidence']}"
            ],
            "evidence_ledger": ledger,
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
         unavailable, along with event log entries and the updated evidence ledger.
    """
    classification = state.get("intent_classification")
    if classification:
        ledger = update_agent_ledger(
            state,
            agent_name="intent_classifier",
            step_name="finalize",
            status="success",
            output_summary={
                "kind": "intent_classification",
                "intent": classification.get("intent"),
                "confidence": classification.get("confidence"),
            },
        )
        return {"intent_classification": classification, "evidence_ledger": ledger}
    fallback = fallback_intent_classification()
    ledger = update_agent_ledger(
        state,
        agent_name="intent_classifier",
        step_name="fallback",
        status="used",
        output_summary={
            "kind": "intent_classification",
            "intent": fallback.get("intent"),
            "confidence": fallback.get("confidence"),
        },
    )
    return {
        "intent_classification": fallback,
        "event_log": ["intent_classifier:fallback_continue"],
        "evidence_ledger": ledger,
    }
