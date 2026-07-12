from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent

# local imports
from app.airag.llm_models.llm_models import get_openai_llm
from app.airag.chains.crag.crag import make_crag, CRAGState
from app.airag.retrieval.retrievers import make_hybrid_retriever
from app.airag.prompts.neg_prompts.md_loader import COACH_PROMPT, COUNTERPART_PROMPT, EVALUATOR_PROMPT

# Choose an llm model for the agent
agent_model = get_openai_llm("gpt-4o", temperature=0.)

# Get the retriever object that will be used in the CRAG graph
retriever = make_hybrid_retriever(vector_store=None, 
                                  documents=[], 
                                  k=4) 
# Create the CRAG instance
crag = make_crag(retriever_obj=retriever,
                 state_schema=CRAGState)

### ---------------------------- TOOLS ----------------------------- ###

@tool
def crag_tool(question: str) -> str:
    """
    Answer a question using the CorrectiveRAG graph.
    """
    result = crag.invoke({
        "question": question,
        "attempts": 0,
    })

    return result["answer"]

### -------------------------------  ------------------------------- ###

# Coach Agent 
agent = create_agent(
    model=agent_model,
    tools=[crag_tool],
    system_prompt=COACH_PROMPT,
    checkpointer=MemorySaver(), #state persistence
    name="Coach Agent"
)
 
config = {'configurable': {'thread_id': 'agent-9-1'}}

# Counterpart Agent
counterpart_agent = create_agent(
    model=agent_model,
    tools=[],
    system_prompt=COUNTERPART_PROMPT,
    checkpointer=MemorySaver(), #state persistence
    name="Counterpart Agent"
)

# Evaluator Agent
evaluator_agent = create_agent(
    model=agent_model,
    tools=[crag_tool],
    system_prompt=EVALUATOR_PROMPT,
    checkpointer=MemorySaver(), #state persistence
    name="Evaluator Agent"
)
