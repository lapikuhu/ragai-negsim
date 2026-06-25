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


def _make_tavily_search(ask_data: SimulationLearnerAskRequest) -> TavilySearch | None:
    """
    Create a Tavily search runnable only when the API key is configured.
    Args:
        ask_data: The learner ask request data containing search parameters.
    Returns:
        A TavilySearch instance if the API key is configured, otherwise None.
    """
    if not settings.TAVILY_API_KEY:
        return None
    return TavilySearch(
        max_results=ask_data.max_results,
        include_images=ask_data.include_images,
        include_answer=ask_data.include_answers,
    )


async def ask_simulation_learner_srvc(
    simulation: Simulation,
    ask_data: SimulationLearnerAskRequest,
    session: AsyncSession,
    current_user: User,
) -> SimulationLearnerAskResponse:
    """
    Ask the learner agent for on-demand advice without mutating simulation state.
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
    learner_state = project_simulation_learner_state(state)

    retrieval_strategy, retrieval_graph = await _get_retrieval_graph_for_simulation(
        simulation,
        session,
    )
    crag_graph = retrieval_graph if retrieval_strategy == "crag" else None
    graph_rag_graph = retrieval_graph if retrieval_strategy == "graphrag" else None

    learner_selection = normalize_llm_selection(
        ask_data.learner_llm_provider,
        ask_data.learner_llm_model,
    )
    learner_model = _build_selected_llm(learner_selection, "simulation.learner")
    tavily_search = _make_tavily_search(ask_data)
    usage_handler, public_usage_handler, usage_config = create_usage_tracking_context(
        tags=["service:simulation_learner", "agent:simulation_learner"],
        metadata=_usage_metadata_for_state(state),
        run_name="simulation.learner",
    )

    summary_available = bool(
        learner_state.get("user_side")
        and (learner_state.get("messages") or learner_state.get("offer_history"))
    )
    agent = make_learner_agent(
        model=learner_model,
        crag_graph=crag_graph,
        graph_rag_graph=graph_rag_graph,
        summarize_model=learner_model,
        messages=learner_state.get("messages", []),
        user_side=learner_state.get("user_side", ""),
        public_context=learner_state.get("scenario_public_context", {}),
        student_private_context=learner_state.get("student_private_context", {}),
        current_offer=learner_state.get("current_offer", {}),
        offer_history=learner_state.get("offer_history", []),
        tavily_search=tavily_search,
        tavily_summarizer_model=learner_model if tavily_search is not None else None,
        include_images=ask_data.include_images,
        include_answers=ask_data.include_answers,
        prompt_template=_render_learner_context_prompt(learner_state),
    )
    agent_result = invoke_with_config(
        agent,
        {"messages": [{"role": "user", "content": ask_data.query}]},
        usage_config,
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
        "context": ask_data.context,
    }
    return SimulationLearnerAskResponse(
        simulation_id=simulation.id,
        status=simulation.status,
        answer=answer,
        metadata=metadata,
    )
