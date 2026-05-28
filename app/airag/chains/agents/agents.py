from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent

# local imports
from app.core.config import settings
from app.airag.llm_models.llm_models import choose_llm_model

# Choose an llm model for the agent
agent_model = choose_llm_model("gpt-4o", temperature=0.)

### ---------------------------- TOOLS ----------------------------- ###
@tool
def crag_tool():
    """
    A tool that runs the CRAG graph on a given question, using the provided 
    retriever and other necessary components. 
    """
    pass

 
agent = create_agent(
    model=agent_model,
    tools=[crag_tool],
    system_prompt='',
    checkpointer=MemorySaver(), #state persistence
)
 
config = {'configurable': {'thread_id': 'agent-9-1'}}
