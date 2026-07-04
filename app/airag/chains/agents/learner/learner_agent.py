import json
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from langsmith import traceable
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field, conint #!! warning "Discouragedin favor of using Annotated with [Field][pydantic.fields.Field] instead.

# local imports
from app.airag.llm_models.llm_models import get_openai_llm
from app.airag.chains.agents.learner.learner_helpers import (
    LEARNER_AGENT_PROMPT,
    render_negotiation_summary_prompt,
    render_learner_agent_prompt,
    render_tavily_summary_prompt,
)
from app.airag.observability.evidence_ledger import source_cards_from_documents
from app.airag.observability.llm_usage import extend_runnable_config, invoke_with_config
from app.core.config import Settings

# Tavily API key from environment
TAVILY_API_KEY = Settings().TAVILY_API_KEY

# ------------------------------ TOOLS ------------------------------- #
### -------------------------- CRAG TOOL --------------------------- ###
class LearnerCragToolInput(BaseModel):
    """
    Input schema for the learner CRAG retrieval tool.
    """
    question: str = Field(description="The learner's negotiation-related question.")


class LearnerStructuredOutput(BaseModel):
    answer: str = Field(description="Learner-facing answer to show to the user.")
    tool_decision_summary: str = Field(
        description="Concise diagnostic summary of tool decisions, not chain-of-thought."
    )
    evidence_used: list[str] = Field(
        default_factory=list,
        description="Short labels for evidence sources used in the answer.",
    )
    confidence: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Confidence in the answer based on available context and tool results.",
    )

# Helper Candidate
def _json_tool_payload(payload: dict[str, Any]) -> str:
    """
    Convert a dictionary payload into a JSON string.
    Args:
        payload (dict): The dictionary to be converted.
    Returns:
        str: The JSON string representation of the payload.
    """
    return json.dumps(payload, default=str, ensure_ascii=False)

# Helper Candidate
def _sources_from_retrieval_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Try to extract sources from a retrieval result dictionary.
    Args:
        result (dict): The result dictionary from a retrieval invocation.
    Returns:
        list: A list of source dictionaries, or an empty list if none found.
    """
    sources = result.get("sources")
    if isinstance(sources, list):
        return sources

    evidence_ledger = result.get("evidence_ledger", {})
    if isinstance(evidence_ledger, dict) and isinstance(evidence_ledger.get("sources"), list):
        return evidence_ledger["sources"]

    documents = result.get("documents", [])
    if isinstance(documents, list):
        return source_cards_from_documents(documents)
    return []


def make_crag_tool(crag_graph: Any) -> StructuredTool:
    """
    Factory to create a learner CRAG tool bound to a supplied retrieval graph.
    Args:
        crag_graph: The compiled CRAG-compatible graph to invoke.
    Returns:
        A StructuredTool that only exposes a question argument to the model.
    """
    def run_crag_tool(question: str) -> str:
        try:
            invoke_config = extend_runnable_config(
                tags=["agent:simulation_learner", "graph:crag", "node:retrieve_context"],
                metadata={
                    "agent": "simulation_learner",
                    "graph": "crag",
                    "node": "retrieve_context",
                },
                run_name="learner.crag",
            )
            result = invoke_with_config(
                crag_graph,
                {
                    "question": question,
                    "attempts": 0,
                },
                invoke_config,
            )
        except Exception as exc: # Return a structured failure payload if the CRAG invocation fails
            return _json_tool_payload(
                {
                    "status": "failed",
                    "answer": "",
                    "context": "",
                    "sources": [],
                    "error": str(exc),
                }
            )

        if not isinstance(result, dict): # Catch non-dict results and wrap them in a dict with default values
            result = {"answer": str(result), "context": "", "evidence_ledger": {}}

        return _json_tool_payload(
            {
                "status": "success",
                "answer": result.get("answer", ""),
                "context": result.get("context", ""),
                "sources": _sources_from_retrieval_result(result),
                "evidence_ledger": result.get("evidence_ledger", {}),
            }
        )
    # StructuredTool wrapping on our factory
    return StructuredTool.from_function(
        func=run_crag_tool,
        name="crag_tool",
        description=(
            "Answer a learner question using the available CorrectiveRAG "
            "retrieval graph and return structured JSON grounding."
        ),
        args_schema=LearnerCragToolInput,
    )


### --------------------- GraphRAG TOOL ---------------------------- ###

def make_graph_rag_tool(graph_rag_instance: Any) -> StructuredTool:
    """
    Factory to create a learner GraphRAG tool bound to a supplied retrieval graph.
    Args:
        graph_rag_instance: The compiled GraphRAG-compatible graph to invoke.
    Returns:
        A StructuredTool that only exposes a question argument to the model.
    """
    def run_graph_rag_tool(question: str) -> str:
        try:
            invoke_config = extend_runnable_config(
                tags=["agent:simulation_learner", "graph:graphrag", "node:retrieve_context"],
                metadata={
                    "agent": "simulation_learner",
                    "graph": "graphrag",
                    "node": "retrieve_context",
                },
                run_name="learner.graphrag",
            )
            result = invoke_with_config(
                graph_rag_instance,
                {
                    "question": question,
                    "attempts": 0,
                },
                invoke_config,
            )
        except Exception as exc: # Return a structured failure payload if the GraphRAG invocation fails
            return _json_tool_payload(
                {
                    "status": "failed",
                    "answer": "",
                    "context": "",
                    "sources": [],
                    "error": str(exc),
                }
            )

        if not isinstance(result, dict): # Catch non-dict results and wrap them in a dict with default values
            result = {"answer": str(result), "context": "", "evidence_ledger": {}}

        return _json_tool_payload(
            {
                "status": "success",
                "answer": result.get("answer", ""),
                "context": result.get("context", ""),
                "sources": _sources_from_retrieval_result(result),
                "evidence_ledger": result.get("evidence_ledger", {}),
            }
        )
    # StructuredTool wrapping on our factory
    return StructuredTool.from_function(
        func=run_graph_rag_tool,
        name="graph_rag_tool",
        description=(
            "Answer a learner question using the available GraphRAG "
            "retrieval graph and return structured JSON grounding."
        ),
        args_schema=LearnerCragToolInput,
    )

### -------------- SUMMARIZE NEGOTIATION HISTORY TOOL -------------- ###
class LearnerNegotiationSummaryInput(BaseModel):
    """
    Input schema for the learner negotiation history summary tool.
    """
    focus: str | None = Field(
        default=None,
        description="Optional area to emphasize in the negotiation summary.",
    )


def _string_list(value: Any) -> list[str]:
    """
    Convert a value to a list of strings.
    Args:
        value: The value to convert, which can be a string, list, or 
            other type.
    Returns:
        list: A list of strings derived from the input value.
    """
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _coerce_summary_result(result: Any) -> dict[str, Any]:
    if hasattr(result, "content"):
        """
        Coerce the summary result into a standardized dictionary format.
        Args:
            result: The result to coerce, which can be a string, dict, 
                or object with a 'content' attribute.
        Returns:
            dict: A dictionary containing the summary, key points, and 
            open questions.
        """
        result = result.content

    if isinstance(result, dict):
        return {
            "summary": str(result.get("summary", "") or ""),
            "key_points": _string_list(result.get("key_points", [])),
            "open_questions": _string_list(result.get("open_questions", [])),
        }

    if isinstance(result, str):
        stripped = result.strip()
        if stripped:
            try: # Attempt to parse the string as JSON and coerce it into the expected format
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                return {
                    "summary": stripped,
                    "key_points": [],
                    "open_questions": [],
                }
            if isinstance(decoded, dict):
                return _coerce_summary_result(decoded)
        return {"summary": stripped, "key_points": [], "open_questions": []}

    return {
        "summary": str(result),
        "key_points": [],
        "open_questions": [],
    }


def make_summarize_negotiation_history_tool(
    *,
    summarize_model: Any,
    messages: list[Any] | None = None,
    user_side: str = "",
    public_context: Any = None,
    student_private_context: Any = None,
    current_offer: Any = None,
    offer_history: list[Any] | None = None,
    summarize_prompt: str | None = None,
) -> StructuredTool:
    """
    Create a learner-safe negotiation history summary tool.
    Args:
        summarize_model: The model used to summarize negotiation history.
        messages: Learner-visible negotiation transcript messages.
        user_side: The learner-controlled side.
        public_context: Public scenario context.
        student_private_context: Private context for the learner side.
        current_offer: The current offer.
        offer_history: Offer history available to the learner.
        summarize_prompt: Optional summarizer prompt template override.
    Returns:
        A StructuredTool exposing only an optional focus argument.
    """
    def run_summary_tool(focus: str | None = None) -> str:
        """
        Run the negotiation history summary tool with an optional focus.
        Args:
            focus: Optional area to emphasize in the negotiation summary.
        Returns:
            A JSON string with the summary, key points, and open questions.
        """
        try: # Render the final summarization prompt
            prompt = render_negotiation_summary_prompt(
                messages=messages,
                user_side=user_side,
                public_context=public_context,
                student_private_context=student_private_context,
                current_offer=current_offer,
                offer_history=offer_history,
                focus=focus,
                prompt_template=summarize_prompt,
            )
            invoke_config = extend_runnable_config(
                tags=["agent:simulation_learner", "node:summarize_negotiation_history"],
                metadata={
                    "agent": "simulation_learner",
                    "node": "summarize_negotiation_history",
                },
                run_name="learner.summarize_negotiation_history",
            )
            result = invoke_with_config(summarize_model, prompt, invoke_config)
            summary_payload = _coerce_summary_result(result)
            return _json_tool_payload(
                {
                    "status": "success",
                    **summary_payload,
                }
            )
        except Exception as exc: # Return a structured failure payload if the summarization fails
            return _json_tool_payload(
                {
                    "status": "failed",
                    "summary": "",
                    "key_points": [],
                    "open_questions": [],
                    "error": str(exc),
                }
            )

    return StructuredTool.from_function(
        func=run_summary_tool,
        name="summarize_negotiation_history_tool",
        description=(
            "Summarize the learner-visible negotiation history and return "
            "structured JSON with a concise summary, key points, and open questions."
        ),
        args_schema=LearnerNegotiationSummaryInput,
    )

### --------------------- TAVILY SEARCH TOOL ----------------------- ###
class LearnerTavilySearchInput(BaseModel):
    """
    Input schema for the learner Tavily web search tool.
    """
    query: str = Field(description="The external web search query.")
    max_results: conint(ge=1) = Field(
        default=5,
        description="Maximum number of web search results to retrieve.",
    )


def _coerce_tavily_summary(result: Any) -> str:
    """
    Coerce the Tavily summarization result into a string summary.
    Args:
        result: The result to coerce, which can be a string, dict, or 
            object with a 'content' attribute.
    Returns:
        str: A string summary extracted from the result.
    """
    if hasattr(result, "content"):
        result = result.content
    if isinstance(result, dict):
        return str(result.get("summary") or result.get("answer") or result)
    return str(result).strip()


def _raw_tavily_results(search_result: Any) -> list[Any]:
    """
    Extract raw results from a Tavily search result.
    Args:
        search_result: The search result to extract from, which can be a dict or list.
    Returns:
        list[Any]: A list of raw search results.
    """
    if isinstance(search_result, dict):
        results = search_result.get("results", [])
        return results if isinstance(results, list) else []
    if isinstance(search_result, list):
        return search_result
    return []


def _normalize_tavily_results(search_result: Any, max_results: int) -> list[dict[str, Any]]:
    """
    Normalize Tavily search results into a list of dictionaries with 
    specific keys.
    Args:
        search_result: The raw search result to normalize.
        max_results: The maximum number of results to include in the 
            normalized list.
    Returns:
        list[dict[str, Any]]: A list of normalized result dictionaries.
    """
    normalized: list[dict[str, Any]] = []
    for item in _raw_tavily_results(search_result)[:max_results]:
        if not isinstance(item, dict):
            continue
        result: dict[str, Any] = {}
        for key in ("title", "url", "content", "score"):
            if key in item:
                result[key] = item[key]
        if result:
            normalized.append(result)
    return normalized


def _sources_from_tavily_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Extract sources from normalized Tavily search results.
    Args:
        results: A list of normalized Tavily search results.
    Returns:
        list[dict[str, Any]]: A list of sources with title and URL.
    """
    sources = []
    for result in results:
        source = {
            key: result[key]
            for key in ("title", "url")
            if key in result
        }
        if source:
            sources.append(source)
    return sources


def make_tavily_search_tool(
    *,
    tavily_search: Any,
    tavily_summarizer_model: Any,
    tavily_summarize_prompt: str | None = None,
    include_images: bool = False,
    include_answers: bool = False #we generate our own summary
) -> StructuredTool:
    """
    Create a learner Tavily search tool bound to search and summarizer deps.
    Args:
        tavily_search: Tavily-compatible runnable exposing invoke.
        tavily_summarizer_model: Model used to summarize normalized results.
        tavily_summarize_prompt: Optional summarization prompt template.
    Returns:
        A StructuredTool exposing only query and max_results.
    """
    def run_tavily_tool(query: str, max_results: int = 5) -> str:
        """
        Run the Tavily search tool with the given query and maximum results.
        Args:
            query: The search query.
            max_results: The maximum number of results to return.
        Returns:
            A JSON string with the search results, summary, and sources.
        """
        try:
            search_config = extend_runnable_config(
                tags=["agent:simulation_learner", "tool:tavily", "node:web_search"],
                metadata={
                    "agent": "simulation_learner",
                    "tool": "tavily",
                    "node": "web_search",
                },
                run_name="learner.tavily.search",
            )
            search_result = invoke_with_config(
                tavily_search,
                {"query": query, 
                 "max_results": max_results,
                 "include_images": include_images,
                 "include_answers": include_answers},
                search_config,
            )
            results = _normalize_tavily_results(search_result, max_results)
            summary_prompt = render_tavily_summary_prompt(
                query=query,
                tavily_results=results,
                prompt_template=tavily_summarize_prompt,
            )
            summary_config = extend_runnable_config(
                tags=["agent:simulation_learner", "tool:tavily", "node:web_search_summary"],
                metadata={
                    "agent": "simulation_learner",
                    "tool": "tavily",
                    "node": "web_search_summary",
                },
                run_name="learner.tavily.summarize",
            )
            summary_result = invoke_with_config(
                tavily_summarizer_model,
                summary_prompt,
                summary_config,
            )
            return _json_tool_payload(
                {
                    "status": "success",
                    "query": query,
                    "summary": _coerce_tavily_summary(summary_result),
                    "results": results,
                    "sources": _sources_from_tavily_results(results),
                }
            )
        except Exception as exc:
            return _json_tool_payload(
                {
                    "status": "failed",
                    "query": query,
                    "summary": "",
                    "results": [],
                    "sources": [],
                    "error": str(exc),
                }
            )

    return StructuredTool.from_function(
        func=run_tavily_tool,
        name="tavily_search_tool",
        description=(
            "Search the web for current or external information and return "
            "structured JSON with a summary, normalized results, and sources."
        ),
        args_schema=LearnerTavilySearchInput,
    )

### ------------------ ASSEMBLE OF AVAILABLE TOOLS ------------------------ ###
def build_learner_tools(crag_graph: Any = None,
                        graph_rag_graph: Any = None,
                        summarize_model: Any = None,
                        messages: list[Any] | None = None,
                        user_side: str = "",
                        public_context: Any = None,
                        student_private_context: Any = None,
                        current_offer: Any = None,
                        offer_history: list[Any] | None = None,
                        summarize_prompt: str | None = None,
                        tavily_search: Any = None,
                        tavily_summarizer_model: Any = None,
                        tavily_summarize_prompt: str | None = None,
                        include_images: bool = False,
                        include_answers: bool = False) -> list[Any]:
    """
    Build the learner tool list based on available runtime dependencies.
    Args:
        crag_graph: Optional CRAG-compatible retrieval graph.
        graph_rag_graph: Optional GraphRAG-compatible retrieval graph.
        summarize_model: Optional model for negotiation history summarization.
        messages: Learner-visible negotiation transcript messages.
        user_side: The learner-controlled side.
        public_context: Public scenario context.
        student_private_context: Private context for the learner side.
        current_offer: The current offer.
        offer_history: Offer history available to the learner.
        summarize_prompt: Optional summarizer prompt template override.
        tavily_search: Optional Tavily-compatible runnable exposing invoke.
        tavily_summarizer_model: Optional model for Tavily result summaries.
        tavily_summarize_prompt: Optional Tavily summary prompt template.
        include_images: Whether to include images in Tavily search results.
        include_answers: Whether to include Tavily summary answer in Tavily search results.
    Returns:
        Tools registered for the learner agent.
    """
    tools: list[Any] = []
    if crag_graph is not None:
        tools.append(make_crag_tool(crag_graph))
    if graph_rag_graph is not None:
        tools.append(make_graph_rag_tool(graph_rag_graph))
    if summarize_model is not None and user_side and (messages or offer_history):
        tools.append(
            make_summarize_negotiation_history_tool(
                summarize_model=summarize_model,
                messages=messages,
                user_side=user_side,
                public_context=public_context,
                student_private_context=student_private_context,
                current_offer=current_offer,
                offer_history=offer_history,
                summarize_prompt=summarize_prompt,
            )
        )
    if tavily_search is not None and tavily_summarizer_model is not None:
        tools.append(
            make_tavily_search_tool(
                tavily_search=tavily_search,
                tavily_summarizer_model=tavily_summarizer_model,
                tavily_summarize_prompt=tavily_summarize_prompt,
                include_images=include_images,
                include_answers=include_answers,
            )
        )
    return tools
# --------------------------- END OF TOOLS --------------------------- #


### ------------------------ DEFINE LEARNER AGENT ------------------------- ###
def make_learner_agent(
    model: Any = None,
    crag_graph: Any = None,
    graph_rag_graph: Any = None,
    summarize_model: Any = None,
    messages: list[Any] | None = None,
    user_side: str = "",
    public_context: Any = None,
    student_private_context: Any = None,
    current_offer: Any = None,
    offer_history: list[Any] | None = None,
    summarize_prompt: str | None = None,
    tavily_search: Any = None,
    tavily_summarizer_model: Any = None,
    tavily_summarize_prompt: str | None = None,
    include_images: bool = False,
    include_answers: bool = False,
    checkpointer: Any = None,
    prompt_template: str | None = None,
) -> Any:
    """
    Create the learner agent with tools matching available dependencies.
    Args:
        model: Optional chat model for the learner. Defaults to gpt-4o.
        crag_graph: Optional CRAG-compatible retrieval graph.
        graph_rag_graph: Optional GraphRAG-compatible retrieval graph.
        summarize_model: Optional model for negotiation history summarization.
        messages: Learner-visible negotiation transcript messages.
        user_side: The learner-controlled side.
        public_context: Public scenario context.
        student_private_context: Private context for the learner side.
        current_offer: The current offer.
        offer_history: Offer history available to the learner.
        summarize_prompt: Optional summarizer prompt template override.
        tavily_search: Optional Tavily-compatible runnable exposing invoke.
        tavily_summarizer_model: Optional model for Tavily result summaries.
        tavily_summarize_prompt: Optional Tavily summary prompt template.
        include_images: Whether to include images in Tavily search results.
        include_answers: Whether to include Tavily summary answer in Tavily search results.
        checkpointer: Optional LangGraph checkpointer.
        prompt_template: Optional base learner prompt template.
    Returns:
        A configured learner agent.
    """
    selected_model = model or get_openai_llm("gpt-4o", temperature=0.)
    selected_summarize_model = summarize_model or selected_model
    summary_available = bool(user_side and (messages or offer_history))
    tavily_available = tavily_search is not None and tavily_summarizer_model is not None
    tools = build_learner_tools(
        crag_graph=crag_graph,
        graph_rag_graph=graph_rag_graph,
        summarize_model=selected_summarize_model if summary_available else None,
        messages=messages,
        user_side=user_side,
        public_context=public_context,
        student_private_context=student_private_context,
        current_offer=current_offer,
        offer_history=offer_history,
        summarize_prompt=summarize_prompt,
        tavily_search=tavily_search,
        tavily_summarizer_model=tavily_summarizer_model,
        tavily_summarize_prompt=tavily_summarize_prompt,
        include_images=include_images,
        include_answers=include_answers,
    )
    system_prompt = render_learner_agent_prompt(
        prompt_template or LEARNER_AGENT_PROMPT,
        crag_available=crag_graph is not None,
        graph_rag_available=graph_rag_graph is not None,
        negotiation_summary_available=summary_available,
        tavily_search_available=tavily_available,
    )
    return create_agent(
        model=selected_model,
        tools=tools,
        system_prompt=system_prompt,
        response_format=LearnerStructuredOutput,
        checkpointer=checkpointer or MemorySaver(),
        name="learner_agent",
    )
### ------------------------ INVOKE LEARNER AGENT ------------------------- ###

@traceable
def invoke_simulation_learner_agent(
    agent: Any,
    question: str,
    config: RunnableConfig | None = None,
) -> Any:
    """
    Invoke the simulation learner agent with a given question.
    Args:
        agent: The learner agent to invoke.
        question: The question to ask the agent.
        config: Optional RunnableConfig for execution settings.
    Returns:
        The learner agent's raw response.
    """
    invoke_config = extend_runnable_config(
        config,
        tags=["agent:simulation_learner", "node:invoke_agent"],
        metadata={
            "agent": "simulation_learner",
            "node": "invoke_agent",
        },
        run_name="simulation_learner.invoke",
    )
    result = invoke_with_config(
        agent,
        {"messages": [{"role": "user", "content": question}]},
        invoke_config,
    )
    return result
