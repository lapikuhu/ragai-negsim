from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired

# local imports
from core.config import settings
from nodes import node_grade, make_crag_retrieve_node, node_rewrite, node_generate, node_fallback, make_decide_after_grade
from routers import make_decide_after_grade

# Define the CRAGState TypedDict to represent the state of the CRAG process
class CRAGState(TypedDict):
    question: str
    attempts: int
    rewritten: NotRequired[str]
    documents: NotRequired[list[Document]]
    answer: NotRequired[str]
    grade: NotRequired[str]
    context: NotRequired[str]
    hallucination_grade: NotRequired[str]
    answer_grade: NotRequired[str]
    quality_reasoning: NotRequired[str]


### --------- Build the CRAG graph --------- ###
def make_crag(ragstate: CRAGState,
              retriever_obj,
              make_retriever_node: callable = make_crag_retrieve_node,
              grader: callable = node_grade,
              rewriter: callable = node_rewrite,
              generator: callable = node_generate,
              fallback: callable = node_fallback,
              make_decider_after_grade: callable = make_decide_after_grade,
              max_rewrite_attempts: int = 2) -> StateGraph:
    """
    Construct the Corrective RAG graph using provided node functions and
    routing logic.
    Args:
        ragstate: The TypedDict representing the state of the RAG process.
        retriever_obj: The retriever instance to use for the retrieve node.
        make_retriever_node: The function to use for creating the retrieve node.
        grader: The function to use for the grade node.
        rewriter: The function to use for the rewrite node.
        generator: The function to use for the generate node.
        fallback: The function to use for the fallback node.
        make_decider_after_grade: The function to use for creating the decider after grade node.
        max_rewrite_attempts: The maximum number of rewrite attempts before falling back.
    Returns:
        A compiled StateGraph representing the CRAG flow.
    """
    # Create the retrieve node with access to the retriever instance
    retriever_node = make_retriever_node(retriever_obj)
    # Create the decider function for routing after grading with the max attempts bound
    decider_after_grade = make_decider_after_grade(max_rewrite_attempts)
    crag_flow = StateGraph(ragstate)
    # Add nodes
    crag_flow.add_node("retrieve",  retriever_node(ragstate))
    crag_flow.add_node("grade",     grader(ragstate))
    crag_flow.add_node("rewrite",   rewriter(ragstate))
    crag_flow.add_node("generate",  generator(ragstate))
    crag_flow.add_node("fallback",  fallback(ragstate))
    # Add edges
    crag_flow.add_edge(START, "retrieve")
    crag_flow.add_edge("retrieve", "grade")
    crag_flow.add_conditional_edges(
    "grade",
    decider_after_grade(ragstate),
    {"generate": "generate", "rewrite": "rewrite", "fallback": "fallback"},
)
    crag_flow.add_edge("rewrite", "retrieve")   # retry loop
    crag_flow.add_edge("generate", END)
    crag_flow.add_edge("fallback", END)

    crag = crag_flow.compile()
    return crag

def make_crag_node(crag):
    """Define a function to execute the CRAG graph given an initial state.
    Args:
        crag: The compiled CRAG StateGraph to execute.
    Returns:
        A function that takes a CRAGState and returns the final answer and
            documents after executing the graph.
    
    """
    def crag_node(state: CRAGState) -> dict:
        """Execute the CRAG graph with the given initial state and return 
        the final answer and documents.
        Args:
            state: The initial CRAGState containing the user's question and any 
                other relevant information.
        Returns:
            A dictionary containing the final answer and the documents used for
                generation.        
        """
        crag_result = crag.invoke({
            "question": state["user_question"]
        })

        return {
            "answer": crag_result["answer"],
            "documents": crag_result.get("documents", []),
        }

    return crag_node






