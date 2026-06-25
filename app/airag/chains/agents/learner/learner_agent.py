from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from langchain_tavily import TavilySearch

# local imports
from app.airag.chains.crag import crag
from app.core.config import settings
from app.airag.llm_models.llm_models import get_openai_llm
from app.airag.chains.agents.learner.learner_helpers import LEARNER_AGENT_PROMPT

# Choose an llm model for the agent
agent_model = get_openai_llm("gpt-4o", temperature=0.)
### ------------------------------ PROMPTS ------------------------------- ###
# TODO: Make more precise, use PCTF format
TAVILY_SUMMARIZE_PROMPT = (
    "You are a precise summarizer. Summarize the following search results "
    "into a concise summary that captures the key points and insights. "
    "Keep the summary factual and avoid adding any information that is not "
    "present in the search results. "
    "Return the summary in a clear and organized manner.\n\n"
    "Search results:\n{tavily_results}\n\n"
    "Summary:\n{summary}"
)
# TODO: Make more precise, use PCTF format
NEGOTIATION_SUMMARIZE_PROMPT = (
    "You are a precise summarizer. Summarize the following negotiation history "
    "into a concise summary that captures the key points and insights. "
    "Keep the summary factual and avoid adding any information that is not "
    "present in the negotiation history. "
    "Return the summary in a clear and organized manner.\n\n"
    "Negotiation history:\n{neg_transcript}\n\n"
    "User side profile:\n{user_side_profile}\n\n"
    "Summary:\n{summary}"
)
### ------------------------------ END OF PROMPTS ------------------------------- ###


### ------------------------------ HELPERS (move) ------------------------------- ###

def summarize_tavily_search_results(tavily_results: list,
                                    tavily_summarize_prompt: str,
                                    tavily_summarizer_model) -> str:
    """
    Summarize the results from TavilySearch.
    Args:
        tavily_results (list): The list of search results from TavilySearch.
        tavily_summarize_prompt (str): The prompt to be used for 
            summarizing tavily results.
        tavily_summarizer_model: The model to be used for summarization.  
    Returns:
        str: A summary of the search results. 
    """
    response = tavily_summarizer_model.invoke({
        "prompt": tavily_summarize_prompt,
        "tavily_results": tavily_results,
    })
    return response["summary"]
### ------------------------------ END OF HELPERS ------------------------------- ###


# ------------------------------ TOOLS ------------------------------- #
### -------------------------- CRAG TOOL --------------------------- ###
@tool
def crag_tool(question: str) -> str:
    """
    Answer a question using the CorrectiveRAG graph.
    Args:
        question (str): The question to be answered.
    Returns:
        str: The answer to the question.
    """
    result = crag.invoke({
        "question": question,
        "attempts": 0,
    })

    return result["answer"]

### -------------- SUMMARIZE NEGOTIATION HISTORY TOOL -------------- ###
@tool
def summarize_negotiation_history_tool(neg_transcript,
                                       user_side_profile,
                                       summarize_prompt) -> str:
    """
    Summarize the negotiation history. Useful when the negotiation history
    is too long, and consumes the context window.
    Args: 
        neg_transcript: the transcript of the negotiation history
        user_side_profile: the profile of the user's side in the negotiation
        summarize_prompt: the prompt to be used for summarization
    Returns:
        str: The summary of the negotiation history.    
    """
    pass

### --------------------- TAVILY SEARCH TOOL ----------------------- ###
@tool
def tavily_search_tool(query: str,
                       max_results:int = 5,
                       tavily_summarizer_model=None,
                       tavily_summarize_prompt=None) -> str:
    """
    Search the web using TavilySearch. Useful for retrieving information
    that is not present in the local knowledge base or CRAG graph.
    Args:
        query (str): The search query.
        max_results (int): The maximum number of search results to return.
        tavily_summarizer_model: The model to be used for Tavily 
            results summarization.
        tavily_summarize_prompt: The prompt to be used for Tavily 
            results summarization.
    Returns:
        str: The search results.
    """
    tavily_search = TavilySearch(max_results = max_results,
                                 include_images = False,
                                 include_videos = False,)
    results = tavily_search.search(query)
    summarized_results = summarize_tavily_search_results(tavily_results=results,
                                                        tavily_summarize_prompt = tavily_summarize_prompt,
                                                        tavily_summarizer_model = tavily_summarizer_model)
    return summarized_results
# --------------------------- END OF TOOLS --------------------------- #


### ------------------------ DEFINE LEARNER AGENT ------------------------- ###
learner_agent = create_agent(
    model=agent_model,
    tools=[crag_tool,
           summarize_negotiation_history_tool,
           tavily_search_tool],
    system_prompt=LEARNER_AGENT_PROMPT,
    checkpointer=MemorySaver(), #state persistence
    name="Learner Agent"
)  