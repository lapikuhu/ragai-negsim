from importlib.resources import files
from typing import Any

from app.airag.chains.agents.helpers import format_messages, json_dumps

def load_prompt(filename: str) -> str:
    """
    Loads a prompt from the specified markdown file.
    Args:
        filename (str): The name of the markdown file to load.
    Returns:
        str: The content of the markdown file as a string.
    """
    return files("app.airag.chains.agents.learner").joinpath("", filename).read_text(encoding="utf-8")

### --------------------------- PROMPTS ---------------------------- ###
LEARNER_AGENT_PROMPT = load_prompt("learner_agent_prompt.md")

# TODO: Make more precise, use PCTF format
TAVILY_SUMMARIZE_PROMPT = (
    "You are a precise learner-facing web search summarizer. Summarize only "
    "the search results below. Keep the summary factual and avoid adding "
    "information that is not present in the search results.\n\n"
    "Search query:\n{query}\n\n"
    "Search results:\n{tavily_results}\n\n"
    "Summary:"
)

NEGOTIATION_SUMMARIZE_PROMPT = (
    "You are a precise learner-facing negotiation transcript summarizer. "
    "Use only the learner-safe context below. Keep the summary factual and "
    "avoid adding information that is not present in the context.\n\n"
    "Return JSON with exactly these keys:\n"
    "- summary: concise paragraph\n"
    "- key_points: list of short strings\n"
    "- open_questions: list of short strings\n\n"
    "Focus:\n{focus}\n\n"
    "User side:\n{user_side}\n\n"
    "Public context:\n{public_context}\n\n"
    "Student private context:\n{student_private_context}\n\n"
    "Current offer:\n{current_offer}\n\n"
    "Offer history:\n{offer_history}\n\n"
    "Negotiation history:\n{messages}"
)
### ------------------------- PROMPTS END -------------------------- ###

def render_tavily_summary_prompt(
    *,
    query: str,
    tavily_results: list[dict[str, Any]],
    prompt_template: str | None = None,
) -> str:
    """
    Render a prompt for summarizing Tavily search results.
    Args:
        query: The web search query.
        tavily_results: Normalized Tavily result dictionaries.
        prompt_template: Optional prompt template override.
    Returns:
        A rendered prompt containing the query and normalized results.
    """
    prompt = prompt_template or TAVILY_SUMMARIZE_PROMPT
    return (
        prompt
        .replace("{query}", query)
        .replace("{tavily_results}", json_dumps(tavily_results))
    )


def render_negotiation_summary_prompt(
    *,
    messages: list[Any] | None = None,
    user_side: str = "",
    public_context: Any = None,
    student_private_context: Any = None,
    current_offer: Any = None,
    offer_history: list[Any] | None = None,
    focus: str | None = None,
    prompt_template: str | None = None,
) -> str:
    """
    Render a learner-safe negotiation summary prompt.
    Args:
        messages: Negotiation transcript messages.
        user_side: The side controlled by the learner.
        public_context: Public scenario context.
        student_private_context: Private context for the learner's side.
        current_offer: The current offer state.
        offer_history: Historical offers.
        focus: Optional summary focus supplied by the learner model.
        prompt_template: Optional prompt template override.
    Returns:
        A rendered prompt containing only learner-safe context.
    """
    replacements = {
        "{focus}": focus or "Overall negotiation progress, concessions, risks, and open questions.",
        "{user_side}": user_side,
        "{public_context}": json_dumps(public_context or {}),
        "{student_private_context}": json_dumps(student_private_context or {}),
        "{current_offer}": json_dumps(current_offer or {}),
        "{offer_history}": json_dumps(offer_history or []),
        "{messages}": format_messages(messages or []),
    }
    prompt = prompt_template or NEGOTIATION_SUMMARIZE_PROMPT
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, str(value))
    return prompt

def render_learner_agent_prompt(
    prompt_template: str | None = None,
    *,
    crag_available: bool = False,
    graph_rag_available: bool = False,
    negotiation_summary_available: bool = False,
    tavily_search_available: bool = False,
) -> str:
    """
    Render the learner prompt with guidance that matches available tools.
    Args:
        prompt_template: The base learner prompt template.
        crag_available: Whether the CRAG retrieval tool is registered.
        graph_rag_available: Whether the GraphRAG retrieval tool is 
            registered.
        negotiation_summary_available: Whether negotiation history
            summarization is registered.
        tavily_search_available: Whether Tavily web search is registered.
    Returns:
        The learner prompt with tool availability guidance appended.
    """
    base_prompt = prompt_template or LEARNER_AGENT_PROMPT
    if crag_available:
        guidance = (
            "Tool availability:\n"
            "- CRAG retrieval is available. Use the crag_tool when a question "
            "needs grounding in negotiation theory or retrieved context."
        )
    else:
        guidance = (
            "Tool availability:\n"
            "- CRAG retrieval is not available. Answer from the provided "
            "conversation and context, and you must not mention CRAG or other "
            "unavailable retrieval tools."
        )
    if graph_rag_available:
        guidance += (
            "\n- GraphRAG retrieval is available. Use the graph_rag_tool when a question "
            "needs grounding in negotiation theory or retrieved context."
        )
    else:
        guidance += (
            "\n- GraphRAG retrieval is not available. Answer from the provided "
            "conversation and context, and you must not mention GraphRAG or other "
            "unavailable retrieval tools."
        )
    if negotiation_summary_available:
        guidance += (
            "\n- Negotiation history summarization is available. Use the "
            "summarize_negotiation_history_tool when the transcript is too long "
            "or the user asks for a compact recap."
        )
    else:
        guidance += (
            "\n- Negotiation history summarization is not available, and you "
            "must not mention the summary tool."
        )
    if tavily_search_available:
        guidance += (
            "\n- Tavily web search is available. Use the tavily_search_tool "
            "only for current or external facts not covered by local retrieval."
        )
    else:
        guidance += (
            "\n- Tavily web search is not available, and you must not mention "
            "web search or Tavily."
        )
    return "\n\n".join([base_prompt, guidance])
