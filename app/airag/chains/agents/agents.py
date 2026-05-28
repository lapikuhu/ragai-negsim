from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent

# local imports
from app.core.config import settings
from app.airag.llm_models.llm_models import choose_llm_model
from app.airag.chains.crag.crag import make_crag, CRAGState
from app.airag.retrieval.retrievers import make_hybrid_retriever
from app.airag.prompts.neg_prompts.md_loader import COACH_PROMPT, COUNTERPART_PROMPT, EVALUATOR_PROMPT

# Choose an llm model for the agent
agent_model = choose_llm_model("gpt-4o", temperature=0.)

# Get the retriever object that will be used in the CRAG graph

retriever = make_hybrid_retriever(vector_store=None, 
                                  documents=[], 
                                  k=4) 
# Create the CRAG instance
crag = make_crag(ragstate=CRAGState,
                retriever_obj=retriever)

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
    system_prompt=COACH_PROMPT,
    checkpointer=MemorySaver(), #state persistence
    name="Coach Agent"
)
 
config = {'configurable': {'thread_id': 'agent-9-1'}}
