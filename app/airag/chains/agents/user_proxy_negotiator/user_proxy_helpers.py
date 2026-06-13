from typing import Any

from app.airag.chains.agents.helpers import (
    append_missing_context_sections,
    format_messages,
    json_dumps,
)
from app.airag.chains.agents.user_proxy_negotiator.user_proxy_model import (
    UserProxyGraphState,
    UserProxyResponseModel,
)
from app.airag.prompts.neg_prompts.md_loader import USER_PROXY_PROMPT


def get_student_private_context(state: UserProxyGraphState) -> dict[str, Any]:
    """Retrieve the student private context from the given graph state.
    Args:
        state: The graph state dictionary.
    Returns:
        A dictionary containing the student private context.
    """
    value = state.get("student_private_context", {})
    return value if isinstance(value, dict) else {}


def get_proxy_persona(state: UserProxyGraphState) -> dict[str, Any]:
    """Retrieve the proxy persona from the given graph state.
    Args:
        state: The graph state dictionary.
    Returns:
        A dictionary containing the proxy persona.
    """
    value = state.get("proxy_persona", {})
    return value if isinstance(value, dict) else {}

# Candidate for agents helpers
def collect_missing_information(state: UserProxyGraphState) -> list[str]:
    """
    Collect missing information from the given graph state.
    Args:
        state: The graph state dictionary.
    Returns:
        A list of missing information keys.
    """
    missing = []
    if not state.get("user_side"):
        missing.append("user_side")
    if not state.get("scenario_public_context"):
        missing.append("scenario_public_context")
    if not state.get("messages"):
        missing.append("messages")
    return missing

# Candidate for agents helpers
def render_user_proxy_prompt(
    state: UserProxyGraphState,
    prompt_template: str | None = None,
) -> str:
    """
    Render the user proxy prompt based on the given graph state and optional prompt template.
    Args:
        state: The graph state dictionary.
        prompt_template: An optional prompt template string.
    Returns:
        A string containing the rendered user proxy prompt.
    """
    replacements = {
        "{public_context}": json_dumps(state.get("scenario_public_context", {})),
        "{student_private_context}": json_dumps(get_student_private_context(state)),
        "{proxy_persona}": json_dumps(get_proxy_persona(state)),
        "{coach_advice}": json_dumps(state.get("coach_advice", {})),
        "{phase}": state.get("phase", ""),
        "{active_side}": state.get("active_side", ""),
        "{messages}": format_messages(state.get("messages", [])),
        "{current_offer}": json_dumps(state.get("current_offer", {})),
        "{offer_history}": json_dumps(state.get("offer_history", [])),
    }

    template = prompt_template or USER_PROXY_PROMPT
    prompt = template
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, str(value))
    return append_missing_context_sections(
        prompt,
        template,
        [
            ("{public_context}", "PUBLIC CONTEXT", state.get("scenario_public_context", {})),
            (
                "{student_private_context}",
                "STUDENT PRIVATE CONTEXT",
                get_student_private_context(state),
            ),
            ("{proxy_persona}", "PROXY PERSONA", get_proxy_persona(state)),
            ("{coach_advice}", "COACH ADVICE", state.get("coach_advice", {})),
        ],
    )


def _collect_secret_strings(value: Any) -> list[str]:
    """
    Recursively collect all secret strings from the given value.
    Args:
        value: The value to collect secret strings from.
    Returns:
        A list of secret strings.
    """
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_collect_secret_strings(item))
        return result
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_collect_secret_strings(item))
        return result
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    return []


def validate_proxy_message_privacy(
    state: UserProxyGraphState,
    response: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate the privacy of the proxy message.
    Args:
        state: The graph state dictionary.
        response: The proxy response dictionary.
    Returns:
        The validated proxy response dictionary.
    Raises:
        ValueError: If the proxy response leaks student private context.
    """
    message = str(response.get("message") or "")
    for secret in _collect_secret_strings(get_student_private_context(state)):
        if secret and secret in message:
            raise ValueError("Proxy response leaked student private context.")
    return response


def coerce_user_proxy_response(result: Any, state: UserProxyGraphState) -> dict[str, Any]:
    """
    Coerce the user proxy response into a validated dictionary.
    Args:
        result: The raw proxy response.
        state: The graph state dictionary.
    Returns:
        A validated proxy response dictionary.
    """
    if isinstance(result, UserProxyResponseModel):
        return validate_proxy_message_privacy(state, result.model_dump())
    if isinstance(result, dict):
        return validate_proxy_message_privacy(
            state,
            UserProxyResponseModel.model_validate(result).model_dump(),
        )
    return validate_proxy_message_privacy(
        state,
        UserProxyResponseModel.model_validate_json(str(result)).model_dump(),
    )


def fallback_user_proxy_response(
    state: UserProxyGraphState,
    reason: str,
) -> dict[str, Any]:
    """
    Generate a fallback user proxy response.
    Args:
        state: The graph state dictionary.
        reason: The reason for using the fallback response.
    Returns:
        A dictionary containing the fallback proxy response.
    """
    scenario_context = state.get("scenario_public_context", {})
    scenario_name = scenario_context.get("name") if isinstance(scenario_context, dict) else None
    coach_advice = state.get("coach_advice", {}) if isinstance(state.get("coach_advice"), dict) else {}
    suggested = coach_advice.get("suggested_response")
    if isinstance(suggested, str) and suggested.strip():
        if scenario_name:
            message = f"In {scenario_name}, {suggested.strip().lower()}"
        else:
            message = suggested.strip()
    elif scenario_name:
        message = (
            f"On {scenario_name}, I want to move this forward, but I need a bit more value "
            "or a clearer trade-off before I can agree."
        )
    else:
        message = "I want to keep this moving, but I need a clearer trade-off before I can agree."
    return {
        "message": message,
        "rationale": f"Fallback proxy response used because: {reason}",
    }


def get_default_user_proxy_model() -> Any | None:
    """
    Get the default user proxy model.
    Returns:
        The default user proxy model or None if not available.
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
