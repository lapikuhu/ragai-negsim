import json
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_tavily import TavilySearch
from sqlmodel.ext.asyncio.session import AsyncSession

from app.airag.chains.agents.context_projections import project_simulation_learner_state
from app.airag.chains.agents.helpers import json_dumps
from app.airag.chains.agents.learner.learner_agent import (
    invoke_simulation_learner_agent,
    make_learner_agent,
)
from app.airag.chains.agents.learner.learner_helpers import LEARNER_AGENT_PROMPT
from app.airag.observability.llm_usage import (
    create_usage_tracking_context,
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
    if hasattr(message, "content"):
        return str(getattr(message, "content") or "")
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


def _message_role_or_type(message: Any) -> tuple[str | None, str | None]:
    """
    Return role name and message type for a LangGraph agent message.
    Args:
        message: The agent message, which can be a BaseMessage or a 
            dictionary.
    Returns:
        A tuple containing the role name and message type, or None if not
    available.
    """
    role = message.get("role") if isinstance(message, dict) else None
    message_type = getattr(message, "type", None)
    return role, message_type


def _message_tool_call_id(message: Any) -> str:
    """
    Return the tool call ID for a LangGraph agent message.
    Args:
        message: The agent message, which can be a BaseMessage or a 
            dictionary.
    Returns:
        A string containing the tool call ID, or an empty string if not
    available.
    """
    value = message.get("tool_call_id") if isinstance(message, dict) else getattr(message, "tool_call_id", "")
    return str(value or "")


def _message_tool_name(message: Any) -> str:
    """
    Return the tool name for a LangGraph agent message.
    Args:
        message: The agent message, which can be a BaseMessage or a 
            dictionary.
    Returns:
        A string containing the tool name, or an empty string if not
    available.
    """
    value = message.get("name") if isinstance(message, dict) else getattr(message, "name", "")
    return str(value or "")


def _message_tool_calls(message: Any) -> list[dict[str, Any]]:
    """
    Return the tool calls for a LangGraph agent message.
    Args:
        message: The agent message, which can be a BaseMessage or a 
            dictionary.
    Returns:
        A list of dictionaries containing the tool calls, or an empty list if not
    available.
    """
    tool_calls = (
        message.get("tool_calls")
        if isinstance(message, dict)
        else getattr(message, "tool_calls", None)
    )
    if not isinstance(tool_calls, list):
        return []
    return [tool_call for tool_call in tool_calls if isinstance(tool_call, dict)]


def _normalize_learner_structured_output(value: Any, *, fallback_answer: str) -> dict[str, Any] | None:
    """
    Normalize the structured output from a learner.
    Args:
        value: The structured output value, which can be a dictionary or 
            an object with a model_dump method.
        fallback_answer: The fallback answer to use if the structured 
            output does not contain an answer.
    Returns:
        A dictionary containing the normalized structured output, or 
        None if the output is not valid.
    """
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if not isinstance(value, dict):
        return None

    answer = str(value.get("answer") or fallback_answer or "").strip()
    if not answer:
        return None

    evidence_used = value.get("evidence_used", [])
    if isinstance(evidence_used, list):
        evidence = [str(item) for item in evidence_used if str(item).strip()]
    elif isinstance(evidence_used, str) and evidence_used.strip():
        evidence = [evidence_used.strip()]
    else:
        evidence = []

    confidence = str(value.get("confidence") or "medium").strip().lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"

    return {
        "answer": answer,
        "tool_decision_summary": str(
            value.get("tool_decision_summary")
            or "Structured learner output did not include a tool decision summary."
        ).strip(),
        "evidence_used": evidence,
        "confidence": confidence,
    }

# Candidate helper
def _parse_structured_json_content(content: str) -> dict[str, Any] | None:
    """
    Parse a string as JSON and return it as a dictionary if valid.
    Args:
        content: The string content to parse as JSON.
    Returns:
        A dictionary if the content is valid JSON and is a dictionary,
        otherwise None.
    """
    try:
        decoded = json.loads(content)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def _extract_learner_structured_output(agent_result: Any) -> dict[str, Any]:
    """
    Extract structured output from a learner's agent result.
    Args:
        agent_result: The result from a LangGraph agent, which can be a 
            dictionary or other types.
    Returns:
        A dictionary containing the structured output, or a fallback answer
        if the structured output is not available.
    """
    fallback_answer = _extract_answer(agent_result)
    if isinstance(agent_result, dict):
        structured = _normalize_learner_structured_output(
            agent_result.get("structured_response"),
            fallback_answer=fallback_answer,
        )
        if structured is not None:
            return structured

        parsed = _parse_structured_json_content(fallback_answer)
        structured = _normalize_learner_structured_output(parsed, fallback_answer=fallback_answer)
        if structured is not None:
            return structured
    # TODO: Define a schema for it
    return {
        "answer": fallback_answer,
        "tool_decision_summary": "Structured learner output was not returned.",
        "evidence_used": [],
        "confidence": "medium",
    }

# TODO: Too brute, LLM should determine what tools are explicitly called for.
def _extract_tool_call_names(agent_result: Any) -> list[str]:
    """
    Extract ordered tool call names from assistant messages in an agent result.
    Args:
        agent_result: The result from a LangGraph agent, which can be a 
            dictionary or other types.
    Returns:
        A list of tool call names in the order they were called by the 
        assistant.
    """
    if not isinstance(agent_result, dict):
        return []
    messages = agent_result.get("messages")
    if not isinstance(messages, list):
        return []

    tool_call_names: list[str] = []
    for message in messages:
        role, message_type = _message_role_or_type(message)
        if role not in {"assistant", "ai"} and message_type not in {"assistant", "ai"}:
            continue

        for tool_call in _message_tool_calls(message):
            name = tool_call.get("name")
            if isinstance(name, str) and name:
                tool_call_names.append(name)
    return tool_call_names


TOOL_REQUEST_ALIASES = {
    "crag_tool": ("crag", "crag_tool"),
    "graph_rag_tool": ("graphrag", "graph rag", "graph_rag_tool"),
    "summarize_negotiation_history_tool": (
        "summary",
        "summarize",
        "summarize_negotiation_history_tool",
    ),
    "tavily_search_tool": (
        "tavily",
        "web search",
        "search the web",
        "tavily_search_tool",
    ),
}


def _explicit_tool_request_metadata(query: str, tools_available: list[str]) -> dict[str, Any]:
    """
    Log explicit tool requests from the user query and check against available tools.
    Args:
        query: The user query string.
        tools_available: A list of available tool names.
    Returns:
        A dictionary containing whether any tools were requested, the names of
        requested tools that are available, and the names of requested tools that
        are unavailable.
    """
    normalized_query = query.lower().replace("-", " ").replace("_", " ")
    requested: list[str] = []
    for tool_name, aliases in TOOL_REQUEST_ALIASES.items():
        if any(alias.lower().replace("_", " ") in normalized_query for alias in aliases):
            requested.append(tool_name)

    available = set(tools_available)
    return {
        "requested": bool(requested),
        "tool_names": [tool_name for tool_name in requested if tool_name in available],
        "unavailable_tool_names": [tool_name for tool_name in requested if tool_name not in available],
    }


def _tool_result_status(content: str) -> str:
    """
    Determine the status of a tool result based on its content.
    Args:
        content: The content of the tool result message.
    Returns:
        A string representing the status of the tool result ("success" 
        or "failed").
    """
    try:
        decoded = json.loads(content)
    except json.JSONDecodeError:
        return "success"
    if isinstance(decoded, dict):
        status = str(decoded.get("status") or "").strip().lower()
        if status in {"success", "failed"}:
            return status
    return "success"


def _extract_learner_debug_events(agent_result: Any) -> list[dict[str, Any]]:
    """
    Extract debug events from the agent result.
    Args:
        agent_result: The result from the agent containing messages and 
        tool calls.
    Returns:
        A list of dictionaries representing the debug events.
    """
    if not isinstance(agent_result, dict):
        return []
    messages = agent_result.get("messages")
    if not isinstance(messages, list):
        return []

    events: list[dict[str, Any]] = []
    tool_names_by_id: dict[str, str] = {}
    for message in messages:
        role, message_type = _message_role_or_type(message)
        if role in {"assistant", "ai"} or message_type in {"assistant", "ai"}:
            for tool_call in _message_tool_calls(message):
                tool_name = str(tool_call.get("name") or "")
                tool_call_id = str(tool_call.get("id") or "")
                if tool_call_id and tool_name:
                    tool_names_by_id[tool_call_id] = tool_name
                events.append(
                    {
                        "type": "tool_call",
                        "tool_name": tool_name,
                        "tool_call_id": tool_call_id,
                        "args": tool_call.get("args") if isinstance(tool_call.get("args"), dict) else {},
                    }
                )
            continue

        if role == "tool" or message_type == "tool":
            content = _agent_message_content(message)
            tool_call_id = _message_tool_call_id(message)
            tool_name = _message_tool_name(message) or tool_names_by_id.get(tool_call_id, "")
            events.append(
                {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "status": _tool_result_status(content),
                    "content": content,
                    "content_length": len(content),
                }
            )
    return events


def _learner_debug_trace(
    agent_result: Any,
    *,
    query: str,
    tools_available: list[str],
) -> dict[str, Any]:
    """
    Generate a debug trace for the learner.
    Args:
        agent_result: The result from the agent containing messages and 
            tool calls.
        query: The query string used in the learner.
        tools_available: A list of available tool names.
    Returns:
        A dictionary containing the explicit tool request metadata and 
        the extracted debug events.
    """
    return {
        "explicit_tool_request": _explicit_tool_request_metadata(query, tools_available),
        "events": _extract_learner_debug_events(agent_result),
    }


def _answer_token_usage_for_metadata(llm_usage: dict[str, Any]) -> dict[str, int]:
    """
    Extract the token usage from the LLM usage metadata.
    Args:
        llm_usage: The LLM usage metadata containing token counts.
    Returns:
        A dictionary containing the total token count.
    """
    totals = llm_usage.get("totals") if isinstance(llm_usage, dict) else None
    total_tokens = totals.get("total_tokens") if isinstance(totals, dict) else 0
    return {"total_tokens": int(total_tokens or 0)}


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
    # Invoke the learner agent with the user's query and the configured settings
    agent_result = invoke_simulation_learner_agent(
        agent,
        ask_data.query,
        config=_learner_invoke_config(
            usage_config,
            simulation_id=simulation.id,
            user_id=current_user.id,
        ),
    )
    learner_structured_output = _extract_learner_structured_output(agent_result)
    answer = learner_structured_output["answer"]
    if not answer:
        raise ValueError("Learner response was empty")

    tools_available = _tool_names_for_metadata(
        retrieval_strategy=retrieval_strategy,
        summary_available=summary_available,
        tavily_available=tavily_search is not None,
    )
    token_usage = summarize_agent_token_usage_handler(public_usage_handler)
    llm_usage = summarize_usage_handler(usage_handler)
    metadata = {
        "tools_available": tools_available,
        "llm_usage": llm_usage,
        "token_usage": token_usage,
        "answer_token_usage": _answer_token_usage_for_metadata(llm_usage),
        "learner_structured_output": learner_structured_output,
        "learner_debug_trace": _learner_debug_trace(
            agent_result,
            query=ask_data.query,
            tools_available=tools_available,
        ),
        "model_selection": learner_selection,
        "tool_calls": _extract_tool_call_names(agent_result),
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
