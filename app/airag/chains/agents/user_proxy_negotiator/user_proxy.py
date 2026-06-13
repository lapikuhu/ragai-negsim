from typing import Any

from langgraph.graph import END, START, StateGraph

from app.airag.chains.agents.context_projections import project_user_proxy_state
from app.airag.chains.agents.user_proxy_negotiator.user_proxy_helpers import (
    get_default_user_proxy_model,
)
from app.airag.chains.agents.user_proxy_negotiator.user_proxy_model import (
    UserProxyGraphState,
)
from app.airag.chains.agents.user_proxy_negotiator.user_proxy_nodes import (
    decide_after_generate,
    decide_after_repair,
    make_generate_user_proxy_response_node,
    make_repair_user_proxy_response_node,
    node_fallback_user_proxy_response,
    node_finalize_user_proxy,
    node_prepare_user_proxy_context,
)
from app.airag.chains.negotiation.negotiation_model import ParentNegotiationState


def make_user_proxy_graph(
    model: Any = None,
    prompt_template: str | None = None,
    state_schema: type[UserProxyGraphState] = UserProxyGraphState,
):
    """
    Create a user proxy graph.
    Args:
        model: The user proxy model.
        prompt_template: The prompt template for the user proxy.
        state_schema: The state schema for the user proxy graph.
    Returns:
        The compiled user proxy graph.
    """
    user_proxy_model = model or get_default_user_proxy_model()

    user_proxy_flow = StateGraph(state_schema)
    user_proxy_flow.add_node("prepare_context", node_prepare_user_proxy_context)
    user_proxy_flow.add_node(
        "generate_proxy_response",
        make_generate_user_proxy_response_node(user_proxy_model, prompt_template),
    )
    user_proxy_flow.add_node(
        "repair_proxy_response",
        make_repair_user_proxy_response_node(user_proxy_model, prompt_template),
    )
    user_proxy_flow.add_node("fallback_proxy_response", node_fallback_user_proxy_response)
    user_proxy_flow.add_node("finalize_proxy", node_finalize_user_proxy)

    user_proxy_flow.add_edge(START, "prepare_context")
    user_proxy_flow.add_edge("prepare_context", "generate_proxy_response")
    user_proxy_flow.add_conditional_edges(
        "generate_proxy_response",
        decide_after_generate,
        {
            "finalize": "finalize_proxy",
            "repair": "repair_proxy_response",
            "fallback": "fallback_proxy_response",
        },
    )
    user_proxy_flow.add_conditional_edges(
        "repair_proxy_response",
        decide_after_repair,
        {
            "finalize": "finalize_proxy",
            "fallback": "fallback_proxy_response",
        },
    )
    user_proxy_flow.add_edge("fallback_proxy_response", "finalize_proxy")
    user_proxy_flow.add_edge("finalize_proxy", END)

    return user_proxy_flow.compile()


def make_user_proxy_node(user_proxy_graph: Any):
    def user_proxy_node(state: ParentNegotiationState) -> dict:
        result = user_proxy_graph.invoke(project_user_proxy_state(state))
        return {
            "proxy_response": result.get("proxy_response", {}),
            "event_log": result.get("event_log", []),
        }

    return user_proxy_node


async def invoke_user_proxy_turn(
    state: ParentNegotiationState,
    persona: Any | None,
    duration: str,
    user_proxy_graph: Any | None = None,
) -> dict[str, Any]:
    """
    Invoke a user proxy turn.
    Args:
        state: The parent negotiation state.
        persona: The user proxy persona.
        duration: The duration of the proxy turn.
        user_proxy_graph: The user proxy graph.
    Returns:
        A dictionary containing the user proxy response.
    """
    graph = user_proxy_graph or make_user_proxy_graph()
    proxy_state = project_user_proxy_state(
        {
            **state,
            "user_proxy_persona": {
                key: value
                for key, value in {
                    "id": getattr(persona, "id", None),
                    "name": getattr(persona, "name", None),
                    "description": getattr(persona, "description", None),
                }.items()
                if value is not None
            },
            "proxy_duration": duration,
        }
    )
    result = graph.invoke(proxy_state)
    return result.get("proxy_response", {})
