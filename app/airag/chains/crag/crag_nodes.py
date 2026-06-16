
# local imports
from langchain_core.runnables.config import RunnableConfig
from langsmith import traceable

from app.airag.chains.crag.helpers import format_docs
from app.airag.chains.crag.helpers import document_grader, rewrite_chain, generation_chain
from app.airag.chains.crag.helpers import detect_injection, fallback_chain
from app.airag.chains.crag.helpers import hallucination_grader, answer_grader
from app.airag.observability.llm_usage import extend_runnable_config, invoke_with_config

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
    @traceable
    def node_retrieve(state, config: RunnableConfig | None = None) -> dict:
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


def make_crag_rerank_node(reranker, top_k: int = 3):
    """
    Rerank retrieved documents before grading and generation.
    """

    def node_rerank(state) -> dict:
        docs = state.get("documents", [])
        if not docs:
            return {"documents": docs}

        question = state.get("rewritten") or state["question"]
        try:
            reranked_docs = reranker(question, docs, top_k)
        except Exception as exc:
            print(f"[rerank] failed, preserving retrieval order: {exc}")
            return {"documents": docs}
        return {"documents": reranked_docs}

    return node_rerank

### --------------------- DOCUMENT GRADER NODE---------------------- ###
@traceable
def node_grade(state, config: RunnableConfig | None = None) -> dict:
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
    invoke_config = extend_runnable_config(
        config,
        tags=["graph:crag", "node:grade_documents", "prompt:document_grader"],
        metadata={"graph": "crag", "node": "grade_documents", "prompt": "document_grader"},
        run_name="crag.grade_documents",
    )
    verdict = invoke_with_config(
        document_grader,
        {"question": question, "context": context},
        invoke_config,
    )
    print(f"[grade] {verdict.relevance} | {verdict.reasoning}")
    return {"grade": verdict.relevance}

### --------------------------- REWRITE ---------------------------- ###
@traceable
def node_rewrite(state, config: RunnableConfig | None = None) -> dict:
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
    invoke_config = extend_runnable_config(
        config,
        tags=["graph:crag", "node:rewrite", "prompt:rewrite"],
        metadata={"graph": "crag", "node": "rewrite", "prompt": "rewrite"},
        run_name="crag.rewrite",
    )
    rewritten = invoke_with_config(
        rewrite_chain,
        {"question": state["question"]},
        invoke_config,
    ).strip()
    attempts = state.get("attempts", 0) + 1
    print(f"[rewrite] attempt={attempts} | rewritten={rewritten!r}")
    return {"rewritten": rewritten, "attempts": attempts}

### -------------------------- QUALITY NODE ------------------------ ###
# Combines hallucination check and answer grading to determine overall quality#
@traceable
def node_quality_check(state, config: RunnableConfig | None = None) -> dict:
    """Define the quality check node which evaluates the generated answer for
    hallucinations and relevance to the question.
    Args:
        state: The current CRAG state containing the question, generated answer,
            and the context used for generation.
    Returns:
        A dictionary containing the hallucination grade, answer relevance grade,
            and reasoning for the quality assessment.
    """
    context = state.get("context") or format_docs(state.get("documents", []))
    trusted_context = state.get("trusted_context", "")
    answer = state.get("answer", "")

    if not answer or (not context and not trusted_context):
        return {
            "hallucination_grade": "no",
            "answer_grade": "no",
            "quality_reasoning": "Missing context or answer.",
        }

    hall_config = extend_runnable_config(
        config,
        tags=["graph:crag", "node:hallucination_check", "prompt:hallucination_grader"],
        metadata={
            "graph": "crag",
            "node": "hallucination_check",
            "prompt": "hallucination_grader",
        },
        run_name="crag.hallucination_check",
    )
    hall = invoke_with_config(
        hallucination_grader,
        {
            "context": context,
            "trusted_context": trusted_context,
            "answer": answer,
        },
        hall_config,
    )
    answer_config = extend_runnable_config(
        config,
        tags=["graph:crag", "node:answer_grade", "prompt:answer_grader"],
        metadata={"graph": "crag", "node": "answer_grade", "prompt": "answer_grader"},
        run_name="crag.answer_grade",
    )
    ans = invoke_with_config(
        answer_grader,
        {"question": state["question"], "answer": answer},
        answer_config,
    )
    reasoning = (
        f"grounded={hall.grounded}; addresses={ans.addresses}; "
        f"trusted_context={'yes' if trusted_context else 'no'}; "
        f"hallucination_reasoning={hall.reasoning}"
    )
    print(f"[quality_check] {reasoning}")

    return {
        "hallucination_grade": hall.grounded,
        "answer_grade": ans.addresses,
        "quality_reasoning": reasoning,
    }

### --------------------------- GENERATE --------------------------- ###
@traceable
def node_generate(state, config: RunnableConfig | None = None) -> dict:
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
    trusted_context = state.get("trusted_context", "")
    invoke_config = extend_runnable_config(
        config,
        tags=["graph:crag", "node:generate", "prompt:generation"],
        metadata={"graph": "crag", "node": "generate", "prompt": "generation"},
        run_name="crag.generate",
    )
    answer = invoke_with_config(
        generation_chain,
        {
            "question": state["question"],
            "context": context,
            "trusted_context": trusted_context,
        },
        invoke_config,
    ).strip()
    return {"answer": answer, "context": context}

### --------------------------- FALLBACK --------------------------- ###
@traceable
def node_fallback(state, config: RunnableConfig | None = None) -> dict:
    """
    Generate a fallback answer when the knowledge base retrieval and rewrite
    attempts did not produce relevant usable context.
    """
    question = state["question"]
    rewritten = state.get("rewritten", "")

    invoke_config = extend_runnable_config(
        config,
        tags=["graph:crag", "node:fallback", "prompt:fallback"],
        metadata={"graph": "crag", "node": "fallback", "prompt": "fallback"},
        run_name="crag.fallback",
    )
    answer = invoke_with_config(
        fallback_chain,
        {
            "question": question,
            "rewritten": rewritten,
        },
        invoke_config,
    ).strip()

    return {
        "answer": answer,
        "context": "",
        "documents": state.get("documents", []),
    }
