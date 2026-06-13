from typing import Any

from app.airag.chains.agents.user_proxy_negotiator.user_proxy_helpers import (
    coerce_user_proxy_response,
    collect_missing_information,
    fallback_user_proxy_response,
    render_user_proxy_prompt,
)
from app.airag.chains.agents.user_proxy_negotiator.user_proxy_model import (
    UserProxyGraphState,
    UserProxyResponseModel,
)


def node_prepare_user_proxy_context(state: UserProxyGraphState) -> dict:
    """
    Prepare the user proxy context.
    Args:
        state: The graph state dictionary.
    Returns:
        A dictionary containing the prepared user proxy context.
    """
    missing_information = collect_missing_information(state)
    return {
        "messages": state.get("messages", []),
        "offer_history": state.get("offer_history", []),
        "proxy_retry_count": state.get("proxy_retry_count", 0),
        "proxy_validation_error": "",
        "missing_information": missing_information,
        "event_log": [
            f"user_proxy:prepared_context missing={','.join(missing_information) or 'none'}"
        ],
    }


def make_generate_user_proxy_response_node(model: Any, prompt_template: str | None = None):
    def node_generate_user_proxy_response(state: UserProxyGraphState) -> dict:
        """
        Generate a user proxy response.
        Args:
            state: The graph state dictionary.
        Returns:
            A dictionary containing the generated user proxy response.
        """
        if model is None:
            return {
                "proxy_validation_error": "User proxy model is not configured.",
                "event_log": ["user_proxy:generation_failed"],
            }

        prompt = render_user_proxy_prompt(state, prompt_template)
        try:
            structured_model = model.with_structured_output(
                UserProxyResponseModel,
                method="function_calling",
            )
            response = coerce_user_proxy_response(structured_model.invoke(prompt), state)
        except Exception as exc:
            return {
                "proxy_prompt": prompt,
                "proxy_validation_error": str(exc),
                "event_log": ["user_proxy:generation_failed"],
            }

        return {
            "proxy_prompt": prompt,
            "proxy_response": response,
            "proxy_validation_error": "",
            "event_log": ["user_proxy:generated_response"],
        }

    return node_generate_user_proxy_response


def make_repair_user_proxy_response_node(model: Any, prompt_template: str | None = None):
    def node_repair_user_proxy_response(state: UserProxyGraphState) -> dict:
        """
        Repair a user proxy response.
        Args:
            state: The graph state dictionary.
        Returns:
            A dictionary containing the repaired user proxy response.
        """
        retry_count = state.get("proxy_retry_count", 0) + 1
        if model is None:
            return {
                "proxy_retry_count": retry_count,
                "proxy_validation_error": "User proxy model is not configured for repair.",
                "event_log": ["user_proxy:repair_failed"],
            }

        repair_prompt = "\n\n".join(
            [
                "Repair the user proxy response so it satisfies the required schema.",
                "Return only structured output.",
                f"Validation or generation error:\n{state.get('proxy_validation_error', '')}",
                f"Original proxy prompt:\n{state.get('proxy_prompt') or render_user_proxy_prompt(state, prompt_template)}",
            ]
        )

        try:
            structured_model = model.with_structured_output(
                UserProxyResponseModel,
                method="function_calling",
            )
            response = coerce_user_proxy_response(structured_model.invoke(repair_prompt), state)
        except Exception as exc:
            return {
                "proxy_retry_count": retry_count,
                "proxy_validation_error": str(exc),
                "event_log": ["user_proxy:repair_failed"],
            }

        return {
            "proxy_response": response,
            "proxy_validation_error": "",
            "proxy_retry_count": retry_count,
            "event_log": ["user_proxy:repaired_response"],
        }

    return node_repair_user_proxy_response


def node_fallback_user_proxy_response(state: UserProxyGraphState) -> dict:
    """
    Generate a fallback user proxy response node.
    Args:
        state: The graph state dictionary.
    Returns:
        A dictionary containing the fallback user proxy response.
    """
    return {
        "proxy_response": fallback_user_proxy_response(
            state,
            state.get("proxy_validation_error", "unknown proxy generation failure"),
        ),
        "event_log": ["user_proxy:fallback"],
    }


def node_finalize_user_proxy(state: UserProxyGraphState) -> dict:
    """
    Finalize the user proxy response node.
    Args:
        state: The graph state dictionary.
    Returns:
        A dictionary containing the finalized user proxy response.
    """
    response = state.get("proxy_response") or fallback_user_proxy_response(
        state,
        "missing proxy_response at finalize",
    )
    return {
        "proxy_response": response,
        "event_log": ["user_proxy:completed"],
    }


def decide_after_generate(state: UserProxyGraphState) -> str:
    """
    Decide the next action after generating a user proxy response.
    Args:
        state: The graph state dictionary.
    Returns:
        The next action as a string.
    """
    if state.get("proxy_response"):
        return "finalize"
    if state.get("proxy_retry_count", 0) < 1:
        return "repair"
    return "fallback"


def decide_after_repair(state: UserProxyGraphState) -> str:
    """
    Decide the next action after repairing a user proxy response.
    Args:
        state: The graph state dictionary.
    Returns:
        The next action as a string.
    """
    if state.get("proxy_response"):
        return "finalize"
    return "fallback"
