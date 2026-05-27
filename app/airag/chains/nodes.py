
# local imports
from helpers import format_docs
from helpers import document_grader, rewrite_chain, generation_chain
from helpers import detect_injection


def node_grade(state) -> dict:
    """
    Define the grade node which evaluates the relevance of the retrieved 
    documents to the question.
    """
    docs = state.get("documents", [])
    if not docs:
        print("[grade] no documents retrieved → not_relevant")
        return {"grade": "not_relevant"}
    question = state.get("rewritten") or state["question"]
    context = format_docs(docs)
    verdict = document_grader.invoke({"question": question, "context": context})
    print(f"[grade] {verdict.relevance} | {verdict.reasoning}")
    return {"grade": verdict.relevance}

def make_crag_retrieve_node(retriever):
    """
    Define a function to create the retrieve node with access to the 
    retriever instance.
    Args:
        retriever: The retriever instance to use for retrieving relevant 
            documents based on the query.
    Returns:
        A function that takes a CRAGState and returns the retrieved documents.
    """
    def node_retrieve(state) -> dict:
        """
        Define the retrieve node which takes the current question (original or 
            rewritten) and retrieves relevant documents from the vector store 
            retriever. This retrieve node is specific to a CRAG architecture.
        Args:
            state: The current RAG state containing the question and any 
                rewritten versions.
        Returns:
            A dictionary containing the retrieved documents.
    """
        query = state.get("rewritten") or state["question"]
        # Check for prompt injection in the query before retrieval
        if detect_injection(query):
            print("[retrieve] Prompt injection detected in query! Returning no documents.")
            return {"documents": []}
        else:
            docs = retriever.invoke(query)
            return {"documents": docs}
    return node_retrieve

def node_grade(state) -> dict:
    """
    Define the grade node which evaluates the relevance of the retrieved 
    documents to the question.
    """
    docs = state.get("documents", [])
    if not docs:
        print("[grade] no documents retrieved → not_relevant")
        return {"grade": "not_relevant"}
    question = state.get("rewritten") or state["question"]
    context = format_docs(docs)
    verdict = document_grader.invoke({"question": question, "context": context})
    print(f"[grade] {verdict.relevance} | {verdict.reasoning}")
    return {"grade": verdict.relevance}

# REWRITE
def node_rewrite(state) -> dict:
    """
    Define the rewrite node which attempts to reformulate the question if 
    the retrieved documents were not relevant.
    Args:
        state: The current RAG state containing the original question and any 
            previous rewritten versions.
    Returns:
        A dictionary containing the rewritten question and the number of
            rewrite attempts.
    """
    rewritten = rewrite_chain.invoke({"question": state["question"]}).strip()
    attempts = state.get("attempts", 0) + 1
    print(f"[rewrite] attempt={attempts} | rewritten={rewritten!r}")
    return {"rewritten": rewritten, "attempts": attempts}

# GENERATE
def node_generate(state) -> dict:
    """
    Define the generate node which produces an answer based on the 
    retrieved documents.
    Args:
        state: The current CRAG state containing the question and retrieved
            documents.
    Returns:
        A dictionary containing the generated answer and the context used for 
            generation.
    """
    docs = state.get("documents", [])
    context = format_docs(docs)
    answer = generation_chain.invoke({
        "question": state["question"],
        "context": context,
    }).strip()
    return {"answer": answer, "context": context}

# FALLBACK
def node_fallback(state) -> dict:
    """
    Define the fallback node which is invoked when the retrieved documents 
    are not relevant and we've exhausted rewrite attempts.
    """
    pass