from typing import Any

from langchain_core.messages import BaseMessage
from langchain_tavily import TavilySearch
from sqlmodel.ext.asyncio.session import AsyncSession

from app.airag.chains.agents.context_projections import project_simulation_learner_state
from app.airag.chains.agents.helpers import json_dumps
from app.airag.chains.agents.learner.learner_agent import make_learner_agent
from app.airag.chains.agents.learner.learner_helpers import LEARNER_AGENT_PROMPT
from app.airag.observability.llm_usage import (
    create_usage_tracking_context,
    invoke_with_config,
    summarize_agent_token_usage_handler,
    summarize_usage_handler,
)
from app.core.config import settings
from app.models.simulations import Simulation
from app.models.users import User
from app.schemas.simulation_learner_schemas import (
    SimulationLearnerChatMessage,
    SimulationLearnerAskRequest,
    SimulationLearnerAskResponse,
)
from app.services.llm_models_service import normalize_llm_selection
from app.services.simulations_service import (
    RUNNABLE_STATUSES,
    _build_selected_llm,
    _get_retrieval_graph_for_simulation,
    _graph_state_from_simulation,
    _usage_metadata_for_state,
)


def _render_learner_context_prompt(state: dict[str, Any]) -> str:
    """
    Render the learner base prompt with learner-safe simulation context.
    Args:
        state: The simulation state dictionary.
    Returns:
        A string containing the rendered prompt with learner-safe context.
    """
    replacements = {
        "{user_side}": state.get("user_side", ""),
        "{public_context}": json_dumps(state.get("scenario_public_context", {})),
        "{student_private_context}": json_dumps(state.get("student_private_context", {})),
        "{phase}": state.get("phase", ""),
        "{active_side}": state.get("active_side", ""),
        "{messages}": json_dumps(state.get("messages", [])),
        "{current_offer}": json_dumps(state.get("current_offer", {})),
        "{offer_history}": json_dumps(state.get("offer_history", [])),
        "{retrieval_context}": json_dumps(state.get("evidence_ledger", {})),
    }
    prompt = LEARNER_AGENT_PROMPT
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, str(value))
    return prompt


def _render_learner_chat_history(chat_history: list[SimulationLearnerChatMessage]) -> str:
    """
    Render the learner chat history into a string format for inclusion in
    the prompt.
    Args:
        chat_history: A list of SimulationLearnerChatMessage objects representing
            the chat history.
    Returns:
        A string containing the formatted chat history, or an empty string if
        there are no messages.
    """
    lines: list[str] = []
    for message in chat_history:
        content = message.content.strip()
        if not content:
            continue
        role_label = "User" if message.role == "user" else "Assistant"
        lines.append(f"{role_label}: {content}")
    if not lines:
        return ""
    return "\n\nPrevious learner conversation:\n" + "\n".join(lines)


def _agent_message_content(message: Any) -> str:
    """
    Convert an agent message to a string representation of its content.
    Args:
        message: The agent message, which can be a BaseMessage or a 
            dictionary.
    Returns:
        A string representation of the message content.
    """
    if isinstance(message, BaseMessage):
        return str(message.content)
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(message)


def _extract_answer(agent_result: Any) -> str:
    """
    Extract the final assistant answer from a LangGraph agent result.
    Args:
        agent_result: The result from a LangGraph agent, which can be a 
            dictionary or other types.
    Returns:
        A string containing the final assistant answer.
    """
    if isinstance(agent_result, dict):
        messages = agent_result.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                role = message.get("role") if isinstance(message, dict) else None
                message_type = getattr(message, "type", None)
                if role in {"assistant", "ai"} or message_type in {"assistant", "ai"}:
                    content = _agent_message_content(message).strip()
                    if content:
                        return content
            if messages:
                return _agent_message_content(messages[-1]).strip()
        for key in ("answer", "output"):
            if agent_result.get(key):
                return str(agent_result[key]).strip()
    return str(agent_result).strip()

# WATCH: Have to manually include the tool names in the metadata
def _tool_names_for_metadata(
    *,
    retrieval_strategy: str | None,
    summary_available: bool,
    tavily_available: bool,
) -> list[str]:
    """
    Get the tool names based on the available metadata.
    Args:
        retrieval_strategy: The retrieval strategy used, which can be 
            "crag" or "graphrag".
        summary_available: Whether a summary tool is available.
        tavily_available: Whether the Tavily search tool is available.
    Returns:
        A list of tool names.
    """
    tools: list[str] = []
    if retrieval_strategy == "crag":
        tools.append("crag_tool")
    if retrieval_strategy == "graphrag":
        tools.append("graph_rag_tool")
    if summary_available:
        tools.append("summarize_negotiation_history_tool")
    if tavily_available:
        tools.append("tavily_search_tool")
    return tools


def _learner_config_from_state(state: dict[str, Any]) -> dict[str, Any]:
    """
    Extract the learner configuration from the given state.
    Args:
        state: The state dictionary containing the learner configuration.
    Returns:
        A dictionary representing the learner configuration.
    """
    raw_config = state.get("learner_config")
    return raw_config if isinstance(raw_config, dict) else {"enabled": False}


def _configured_model_selection(
    learner_config: dict[str, Any],
    model_key: str,
) -> dict[str, str]:
    """
    Get the configured model selection for the given model key.
    Args:
        learner_config: The learner configuration dictionary.
        model_key: The key representing the model selection.
    Returns:
        A dictionary representing the normalized model selection.
    """
    raw_models = learner_config.get("models")
    raw_selection = raw_models.get(model_key) if isinstance(raw_models, dict) else None
    if not isinstance(raw_selection, dict):
        return normalize_llm_selection(None, None)
    return normalize_llm_selection(
        raw_selection.get("provider"),
        raw_selection.get("model"),
    )


def _response_model_selection(
    ask_data: SimulationLearnerAskRequest,
    learner_config: dict[str, Any],
) -> dict[str, str]:
    """
    Get the response model selection based on the ask data and learner 
    configuration.
    Args:
        ask_data: The learner ask request data.
        learner_config: The learner configuration dictionary.
    Returns:
        A dictionary representing the normalized model selection.
    """
    if ask_data.learner_llm_provider is not None or ask_data.learner_llm_model is not None:
        return normalize_llm_selection(
            ask_data.learner_llm_provider,
            ask_data.learner_llm_model,
        )
    return _configured_model_selection(learner_config, "response")


def _request_field_was_set(
    ask_data: SimulationLearnerAskRequest,
    field_name: str,
) -> bool:
    """
    Check if a specific field was set in the ask data.
    Args:
        ask_data: The learner ask request data.
        field_name: The name of the field to check.
    Returns:
        True if the field was set, False otherwise.
    """
    return field_name in ask_data.model_fields_set


def _ask_tavily_settings(
    ask_data: SimulationLearnerAskRequest,
    learner_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Get the Tavily settings based on the ask data and learner configuration.
    Args:
        ask_data: The learner ask request data.
        learner_config: The learner configuration dictionary.
    Returns:
        A dictionary representing the Tavily settings.
    """
    raw_tavily = learner_config.get("tavily")
    stored = raw_tavily if isinstance(raw_tavily, dict) else {}
    return {
        "max_results": ask_data.max_results
        if _request_field_was_set(ask_data, "max_results")
        else stored.get("max_results", ask_data.max_results),
        "include_images": ask_data.include_images
        if _request_field_was_set(ask_data, "include_images")
        else stored.get("include_images", ask_data.include_images),
        "include_answers": ask_data.include_answers
        if _request_field_was_set(ask_data, "include_answers")
        else stored.get("include_answers", ask_data.include_answers),
    }


def _make_configured_tavily_search(tavily_settings: dict[str, Any]) -> TavilySearch | None:
    """
    Create a TavilySearch instance when a Tavily API key is configured.
    Args:
        tavily_settings: A dictionary containing the Tavily settings.
    Returns:
        A TavilySearch instance if the API key is set, otherwise None.
    """
    tavily_api_key = (settings.TAVILY_API_KEY or "").strip()
    if not tavily_api_key:
        return None
    return TavilySearch(
        max_results=int(tavily_settings["max_results"]),
        include_images=bool(tavily_settings["include_images"]),
        include_answer=bool(tavily_settings["include_answers"]),
        tavily_api_key=tavily_api_key,
    )


def _learner_invoke_config(
    usage_config: dict[str, Any],
    *,
    simulation_id: int | None,
    user_id: int | None,
) -> dict[str, Any]:
    """
    Create a configuration dictionary for invoking the learner agent with
    usage tracking and thread identification.
    Args:
        usage_config: The base usage configuration dictionary.
        simulation_id: The ID of the simulation, used for thread
            identification.
        user_id: The ID of the user, used for thread identification.
    Returns:
        A dictionary containing the updated configuration for invoking
        the learner agent.
    """
    config = dict(usage_config)
    configurable = dict(config.get("configurable") or {})
    configurable["thread_id"] = f"simulation-{simulation_id}-learner-user-{user_id}"
    config["configurable"] = configurable
    return config


async def ask_simulation_learner_srvc(
    simulation: Simulation,
    ask_data: SimulationLearnerAskRequest,
    session: AsyncSession,
    current_user: User,
) -> SimulationLearnerAskResponse:
    """
    Ask the learner agent for on-demand advice without mutating simulation state.
    Agent re-built at each invocation, non-persistent mode.
    Args:
        simulation: The simulation object.
        ask_data: The learner ask request data.
        session: The database session.
        current_user: The current user making the request.
    Returns:
        A SimulationLearnerAskResponse containing the answer and metadata.
    Raises:
        ValueError: If the simulation is not active or paused, or if it has 
        ended.
    """
    if simulation.status not in RUNNABLE_STATUSES:
        raise ValueError("Simulation must be active or paused to ask the learner")

    state = _graph_state_from_simulation(simulation)
    if state.get("phase") == "ended":
        raise ValueError("Ended simulations cannot accept learner questions")

    state["user_id"] = str(current_user.id)
    state["user_side"] = simulation.user_side or state.get("user_side") or "side_a"
    state.setdefault("messages", [])
    learner_config = _learner_config_from_state(state)
    if learner_config.get("enabled") is not True:
        raise ValueError("Learning agent is not enabled for this simulation")
    learner_state = project_simulation_learner_state(state)

    retrieval_strategy, retrieval_graph = await _get_retrieval_graph_for_simulation(
        simulation,
        session,
    )
    crag_graph = retrieval_graph if retrieval_strategy == "crag" else None
    graph_rag_graph = retrieval_graph if retrieval_strategy == "graphrag" else None

    learner_selection = _response_model_selection(ask_data, learner_config)
    summary_selection = _configured_model_selection(learner_config, "negotiation_summary")
    tavily_summary_selection = _configured_model_selection(learner_config, "tavily_summary")
    learner_model = _build_selected_llm(learner_selection, "simulation.learner")
    summarize_model = _build_selected_llm(summary_selection, "simulation.learner.summary")
    tavily_settings = _ask_tavily_settings(ask_data, learner_config)
    tavily_search = _make_configured_tavily_search(tavily_settings)
    tavily_summarizer_model = (
        _build_selected_llm(tavily_summary_selection, "simulation.learner.tavily_summary")
        if tavily_search is not None
        else None
    )
    usage_handler, public_usage_handler, usage_config = create_usage_tracking_context(
        tags=["service:simulation_learner", "agent:simulation_learner"],
        metadata=_usage_metadata_for_state(state),
        run_name="simulation.learner",
    )

    summary_available = bool(
        learner_state.get("user_side")
        and (learner_state.get("messages") or learner_state.get("offer_history"))
    )
    prompt_template = _render_learner_context_prompt(learner_state)
    prompt_template += _render_learner_chat_history(ask_data.chat_history)
    agent = make_learner_agent( # Build the learner agent with the appropriate configuration
        model=learner_model,
        crag_graph=crag_graph,
        graph_rag_graph=graph_rag_graph,
        summarize_model=summarize_model,
        messages=learner_state.get("messages", []),
        user_side=learner_state.get("user_side", ""),
        public_context=learner_state.get("scenario_public_context", {}),
        student_private_context=learner_state.get("student_private_context", {}),
        current_offer=learner_state.get("current_offer", {}),
        offer_history=learner_state.get("offer_history", []),
        tavily_search=tavily_search,
        tavily_summarizer_model=tavily_summarizer_model,
        include_images=bool(tavily_settings["include_images"]),
        include_answers=bool(tavily_settings["include_answers"]),
        prompt_template=prompt_template,
    )
    agent_result = invoke_with_config(
        agent,
        {"messages": [{"role": "user", "content": ask_data.query}]},
        _learner_invoke_config(
            usage_config,
            simulation_id=simulation.id,
            user_id=current_user.id,
        ),
    )
    answer = _extract_answer(agent_result)
    if not answer:
        raise ValueError("Learner response was empty")

    tools_available = _tool_names_for_metadata(
        retrieval_strategy=retrieval_strategy,
        summary_available=summary_available,
        tavily_available=tavily_search is not None,
    )
    token_usage = summarize_agent_token_usage_handler(public_usage_handler)
    metadata = {
        "tools_available": tools_available,
        "llm_usage": summarize_usage_handler(usage_handler),
        "token_usage": token_usage,
        "model_selection": learner_selection,
        "model_selections": {
            "response": learner_selection,
            "negotiation_summary": summary_selection,
            "tavily_summary": tavily_summary_selection,
        },
        "tavily": tavily_settings,
        "context": ask_data.context,
        "chat_history_count": len(ask_data.chat_history),
    }
    return SimulationLearnerAskResponse(
        simulation_id=simulation.id,
        status=simulation.status,
        answer=answer,
        metadata=metadata,
    )
