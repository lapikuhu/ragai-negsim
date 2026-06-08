from copy import deepcopy
from typing import Any


IDENTIFIER_FIELDS = (
    "simulation_id",
    "session_id",
    "app_session_id",
    "user_id",
)

NEGOTIATION_FIELDS = (
    "user_side",
    "messages",
    "phase",
    "active_side",
    "current_offer",
    "offer_history",
    "side_a_response",
    "side_b_response",
    "turn_count",
)


def _copy_dict(value: Any) -> dict[str, Any]:
    """
    Helper function to safely copy a dictionary value.
    Args:
    value: The value to copy, expected to be a dictionary.
    Returns:
    A deep copy of the dictionary if the input is a dictionary, otherwise 
    an empty dictionary.
    """
    return deepcopy(value) if isinstance(value, dict) else {}


def _copy_fields(state: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    """
    Helper function to copy specified fields from the state dictionary.
    Args:
        state: The original state dictionary to copy from.
        fields: A tuple of field names to copy from the state.
    Returns:
    A new dictionary containing only the specified fields copied from 
    the state.
    """
    return {
        field: deepcopy(state[field])
        for field in fields
        if field in state
    }


def _latest_user_message(messages: Any) -> Any | None:
    """
    Helper function to extract the latest user message from a list of messages.
    Args:
        messages: The list of messages to search through, expected to be 
            a list of dictionaries or objects representing messages.
    Returns:
        The latest user message if found, otherwise None.
    """
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") in {"user", "human"}:
            return deepcopy(message)
        if getattr(message, "type", None) in {"user", "human"}:
            return deepcopy(message)
    return None


def project_counterpart_state(state: dict[str, Any]) -> dict[str, Any]:
    """
    Projects the state for the counterpart in a negotiation scenario.
    Args:
        state: The original state dictionary to project from.
    Returns:
        A new dictionary representing the projected state for the 
        counterpart.
    """
    user_side = state.get("user_side")
    private_key = (
        "side_a_private_context"
        if user_side == "side_b"
        else "side_b_private_context"
    )
    return {
        **_copy_fields(state, IDENTIFIER_FIELDS + NEGOTIATION_FIELDS),
        "scenario_public_context": _copy_dict(state.get("scenario_public_context")),
        "own_private_context": _copy_dict(state.get(private_key)),
        "counterpart_persona": _copy_dict(state.get("counterpart_persona")),
        "event_log": [],
    }


def project_coach_state(state: dict[str, Any]) -> dict[str, Any]:
    """
    Projects the state for the coach in a negotiation scenario.
    Args:
        state: The original state dictionary to project from.
    Returns:
        A new dictionary representing the projected state for the coach.
    """
    private_key = (
        "side_b_private_context"
        if state.get("user_side") == "side_b"
        else "side_a_private_context"
    )
    return {
        **_copy_fields(state, IDENTIFIER_FIELDS + NEGOTIATION_FIELDS),
        "scenario_public_context": _copy_dict(state.get("scenario_public_context")),
        "student_private_context": _copy_dict(state.get(private_key)),
        "event_log": [],
    }


def project_evaluator_state(state: dict[str, Any]) -> dict[str, Any]:
    """
    Projects the state for the evaluator in a negotiation scenario.
    Args:
        state: The original state dictionary to project from.
    Returns:
        A new dictionary representing the projected state for the evaluator.
    """
    evaluator_fields = (
        *IDENTIFIER_FIELDS,
        *NEGOTIATION_FIELDS,
        "side_a",
        "side_b",
        "coach_advice",
        "evaluation",
        "final_evaluation",
        "retrieval_result",
        "evaluation_mode",
        "terminal_reason",
    )
    return {
        **_copy_fields(state, evaluator_fields),
        "scenario_public_context": _copy_dict(state.get("scenario_public_context")),
        "side_a_private_context": _copy_dict(state.get("side_a_private_context")),
        "side_b_private_context": _copy_dict(state.get("side_b_private_context")),
        "event_log": [],
    }


def project_intent_classifier_state(state: dict[str, Any]) -> dict[str, Any]:
    """
    Projects the state for the intent classifier in a negotiation scenario.
    Args:
        state: The original state dictionary to project from.
    Returns:
        A new dictionary representing the projected state for the intent classifier.
    """
    latest_message = _latest_user_message(state.get("messages"))
    return {
        "messages": [latest_message] if latest_message is not None else [],
        "event_log": [],
    }
