from langchain_core.documents import Document
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired

# local imports
from app.airag.chains.crag.crag_nodes import node_grade, make_crag_retrieve_node, node_rewrite
from app.airag.chains.crag.crag_nodes import node_generate, node_fallback, node_quality_check
from app.airag.chains.crag.crag_nodes import make_crag_rerank_node
from app.airag.chains.crag.crag_routers import make_decide_after_grade, make_decide_after_quality
from app.airag.reranking.reranking import choose_reranker

# Define the CRAGState TypedDict to represent the state of the CRAG process
class CRAGState(TypedDict):
    question: str
    attempts: NotRequired[int]
    rewritten: NotRequired[str]
    documents: NotRequired[list[Document]]
    answer: NotRequired[str]
    grade: NotRequired[str]
    context: NotRequired[str]
    trusted_context: NotRequired[str]
    hallucination_grade: NotRequired[str]
    answer_grade: NotRequired[str]
    quality_reasoning: NotRequired[str]


### --------- Build the CRAG graph --------- ###
def make_crag(retriever_obj,
              state_schema: type[CRAGState] = CRAGState,
              make_retriever_node: callable = make_crag_retrieve_node,
              make_rerank_node: callable = make_crag_rerank_node,
              grader: callable = node_grade,
              rewriter: callable = node_rewrite,
              generator: callable = node_generate,
              quality_check: callable = node_quality_check,
              fallback: callable = node_fallback,
              make_decider_after_grade: callable = make_decide_after_grade,
              make_decider_after_quality: callable = make_decide_after_quality,
              max_rewrite_attempts: int = 2,
              reranker_name: str = "cross_encoder",
              reranker=None,
              rerank_top_k: int = 3) -> StateGraph:
    """
    Construct the Corrective RAG graph using provided node functions and
    routing logic.
    Args:
        state_schema: The TypedDict representing the state of the RAG process.
        retriever_obj: The retriever instance to use for the retrieve node.
        make_retriever_node: The function to use for creating the retrieve node.
        make_rerank_node: The function to use for creating the rerank node.
        grader: The function to use for the grade node.
        rewriter: The function to use for the rewrite node.
        generator: The function to use for the generate node.
        fallback: The function to use for the fallback node.
        make_decider_after_grade: The function to use for creating the decider 
            after grade node.
        make_decider_after_quality: The function to use for creating the decider 
            after quality node.
        max_rewrite_attempts: The maximum number of rewrite attempts before 
            falling back. Default is 2.
        reranker_name: The configured reranker backend when no callable is injected.
        reranker: Optional injected reranker callable for tests or custom backends.
        rerank_top_k: The maximum number of reranked documents to keep.
    Returns:
        A compiled StateGraph representing the CRAG flow.
    """
    if rerank_top_k < 1:
        raise ValueError("rerank_top_k must be at least 1")

    # Create the retrieve node with access to the retriever instance
    retriever_node = make_retriever_node(retriever_obj)
    selected_reranker = reranker or choose_reranker(reranker_name)
    rerank_node = make_rerank_node(selected_reranker, top_k=rerank_top_k)
    # Create the decider function for routing after grading with the max attempts bound
    decider_after_grade = make_decider_after_grade(max_rewrite_attempts)
    # Create the after_quality decider function
    decider_after_quality = make_decider_after_quality(max_rewrite_attempts)
    # Initialize the StateGraph with the initial RAG state
    crag_flow = StateGraph(state_schema)
    # Add nodes
    crag_flow.add_node("retrieve",  retriever_node)
    crag_flow.add_node("rerank",    rerank_node)
    crag_flow.add_node("grade",     grader)
    crag_flow.add_node("rewrite",   rewriter)
    crag_flow.add_node("generate",  generator)
    crag_flow.add_node("quality_check", quality_check)
    crag_flow.add_node("fallback",  fallback)
    # Add edges
    crag_flow.add_edge(START, "retrieve")
    crag_flow.add_edge("retrieve", "rerank")
    crag_flow.add_edge("rerank", "grade")
    crag_flow.add_conditional_edges(
    "grade",
    decider_after_grade,
    {"generate": "generate", "rewrite": "rewrite", "fallback": "fallback"},
)
    crag_flow.add_edge("rewrite", "retrieve")   # retry loop
    crag_flow.add_edge("generate", "quality_check")
    crag_flow.add_conditional_edges(
        "quality_check",
        decider_after_quality,
        {"end": END, "rewrite": "rewrite", "fallback": "fallback"},
    )
    crag_flow.add_edge("fallback", END)
    try:
        crag = crag_flow.compile()
    except Exception as e:
        print(f"Error compiling CRAG graph: {e}")
        raise
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
            "question": state["question"],
            "attempts": state.get("attempts", 0),
            "trusted_context": state.get("trusted_context", ""),
        })

        return {
            "answer": crag_result["answer"],
            "documents": crag_result.get("documents", []),
        }

    return crag_node






