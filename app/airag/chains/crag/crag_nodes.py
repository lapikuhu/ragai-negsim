
# local imports
from langchain_core.runnables.config import RunnableConfig
from langsmith import traceable

from app.airag.chains.crag.helpers import format_docs
from app.airag.chains.crag.helpers import document_grader, rewrite_chain, generation_chain
from app.airag.chains.crag.helpers import fallback_chain
from app.airag.prompt_guard.prompt_guard import detect_injection
from app.airag.chains.crag.helpers import hallucination_grader, answer_grader
from app.airag.observability.evidence_ledger import (
    append_pipeline_step,
    append_quality_check,
    set_sources,
)
from app.airag.observability.llm_usage import extend_runnable_config, invoke_with_config

#### --------------------------- RETRIEVE -------------------------- ###
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
            A dictionary containing the retrieved documents, and the updated 
            evidence ledger after the retrieval step.
    """
        query = state.get("rewritten") or state["question"]
        # Check for prompt injection in the query before retrieval
        if detect_injection(query):
            print("[retrieve] Prompt injection detected in query! Returning no documents.")
            ledger = append_pipeline_step( # Include the blocked retrieval step in the evidence ledger
                state.get("evidence_ledger"),
                name="retrieve",
                status="blocked",
                detail={"query": query, "reason": "prompt_injection_detected"},
            )
            return {"documents": [], "evidence_ledger": ledger}
        else:
            docs = retriever.invoke(query)
            ledger = append_pipeline_step(
                state.get("evidence_ledger"),
                name="retrieve",
                status="success",
                detail={"query": query, "document_count": len(docs)},
            )
            ledger = set_sources(ledger, docs)
            return {"documents": docs, "evidence_ledger": ledger}
    return node_retrieve

### ---------------------------- RERANK ---------------------------- ###
def make_crag_rerank_node(reranker, top_k: int = 3):
    """
    Rerank retrieved documents before grading and generation.
    Args:
        reranker: The reranker function to use for reordering the retrieved 
            documents based on their relevance to the query.
        top_k: The number of top documents to return after reranking.
    Returns:
        A function that takes a CRAGState and returns the reranked documents.
    """

    def node_rerank(state) -> dict:
        """
        Rerank the retrieved documents based on their relevance to the query.
        Args:
            state: The current RAG state containing the question and retrieved
                documents.
        Returns:
            A dictionary containing the reranked documents and the updated
            evidence ledger after the reranking step.
        """
        docs = state.get("documents", [])
        if not docs:
            ledger = append_pipeline_step(
                state.get("evidence_ledger"),
                name="rerank",
                status="skipped",
                detail={"reason": "no_documents"},
            )
            return {"documents": docs, "evidence_ledger": ledger}

        question = state.get("rewritten") or state["question"]
        try:
            reranked_docs = reranker(question, docs, top_k)
        except Exception as exc:
            print(f"[rerank] failed, preserving retrieval order: {exc}")
            ledger = append_pipeline_step(
                state.get("evidence_ledger"),
                name="rerank",
                status="failed",
                detail={"error": str(exc), "preserved_input_order": True},
            )
            ledger = set_sources(ledger, docs)
            return {"documents": docs, "evidence_ledger": ledger}
        ledger = append_pipeline_step(
            state.get("evidence_ledger"),
            name="rerank",
            status="success",
            detail={"top_k": top_k, "input_count": len(docs), "output_count": len(reranked_docs)},
        )
        ledger = set_sources(ledger, reranked_docs)
        return {"documents": reranked_docs, "evidence_ledger": ledger}

    return node_rerank

### --------------------- DOCUMENT GRADER NODE---------------------- ###
def make_node_grade(grader_chain=document_grader):
    @traceable
    def node_grade(state, config: RunnableConfig | None = None) -> dict:
        """
        Define the grade node which evaluates the relevance of the retrieved 
        documents to the question.
        Args:
            state: The current RAG state containing the original question 
                and any previous rewritten versions.
        Returns:
            A dictionary containing the grade of the documents' relevance,
            and the updated evidence ledger after the grading step.
        """
        docs = state.get("documents", [])
        if not docs:
            print("[grade] no documents retrieved → not_relevant")
            ledger = append_quality_check(
                state.get("evidence_ledger"),
                name="document_relevance",
                verdict="not_relevant",
                reasoning="No documents retrieved.",
            )
            ledger = append_pipeline_step(
                ledger,
                name="grade_documents",
                status="success",
                detail={"verdict": "not_relevant"},
            )
            return {"grade": "not_relevant", "evidence_ledger": ledger}
        question = state.get("rewritten") or state["question"]
        context = format_docs(docs)
        invoke_config = extend_runnable_config(
            config,
            tags=["graph:crag", "node:grade_documents", "prompt:document_grader"],
            metadata={"graph": "crag", "node": "grade_documents", "prompt": "document_grader"},
            run_name="crag.grade_documents",
        )
        verdict = invoke_with_config(
            grader_chain,
            {"question": question, "context": context},
            invoke_config,
        )
        print(f"[grade] {verdict.relevance} | {verdict.reasoning}")
        ledger = append_quality_check(
            state.get("evidence_ledger"),
            name="document_relevance",
            verdict=verdict.relevance,
            reasoning=getattr(verdict, "reasoning", ""),
        )
        ledger = append_pipeline_step(
            ledger,
            name="grade_documents",
            status="success",
            detail={"verdict": verdict.relevance},
        )
        return {"grade": verdict.relevance, "evidence_ledger": ledger}
    return node_grade


node_grade = make_node_grade()

### --------------------------- REWRITE ---------------------------- ###
def make_node_rewrite(chain=rewrite_chain):
    @traceable
    def node_rewrite(state, config: RunnableConfig | None = None) -> dict:
        """
        Define the rewrite node which attempts to reformulate the question if 
        the retrieved documents were not relevant.
        Args:
            state: The current RAG state containing the original question and any 
                previous rewritten versions.
        Returns:
            A dictionary containing the rewritten question, the number of
            rewrite attempts, and the updated evidence ledger after the 
            rewrite step.
        """
        invoke_config = extend_runnable_config(
            config,
            tags=["graph:crag", "node:rewrite", "prompt:rewrite"],
            metadata={"graph": "crag", "node": "rewrite", "prompt": "rewrite"},
            run_name="crag.rewrite",
        )
        rewritten = invoke_with_config(
            chain,
            {"question": state["question"]},
            invoke_config,
        ).strip()
        attempts = state.get("attempts", 0) + 1
        print(f"[rewrite] attempt={attempts} | rewritten={rewritten!r}")
        ledger = append_pipeline_step(
            state.get("evidence_ledger"),
            name="rewrite",
            status="success",
            detail={"attempt": attempts, "rewritten": rewritten},
        )
        return {"rewritten": rewritten, "attempts": attempts, "evidence_ledger": ledger}
    return node_rewrite


node_rewrite = make_node_rewrite()

### -------------------------- QUALITY NODE ------------------------ ###
# Combines hallucination check and answer grading to determine overall quality#
def make_node_quality_check(hall_chain=hallucination_grader, ans_chain=answer_grader):
    @traceable
    def node_quality_check(state, config: RunnableConfig | None = None) -> dict:
        """
        Define the quality check node.
        Args:
            state: The current CRAG state containing the question, 
                generated answer, and the context used for generation.
            config: Optional configuration for the runnable.
        Returns:
            A dictionary containing:
            - the hallucination grade
            - the answer relevance grade
            - the reasoning for the quality assessment
            - the updated evidence ledger after the quality check.
        """
        context = state.get("context") or format_docs(state.get("documents", []))
        trusted_context = state.get("trusted_context", "")
        answer = state.get("answer", "")

        if not answer or (not context and not trusted_context):
            ledger = append_quality_check(
                state.get("evidence_ledger"),
                name="groundedness",
                verdict="no",
                reasoning="Missing context or answer.",
            )
            ledger = append_quality_check(
                ledger,
                name="answer_relevance",
                verdict="no",
                reasoning="Missing context or answer.",
            )
            ledger = append_pipeline_step(
                ledger,
                name="quality_check",
                status="failed",
                detail={"reason": "missing_context_or_answer"},
            )
            return {
                "hallucination_grade": "no",
                "answer_grade": "no",
                "quality_reasoning": "Missing context or answer.",
                "evidence_ledger": ledger,
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
            hall_chain,
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
            ans_chain,
            {"question": state["question"], "answer": answer},
            answer_config,
        )
        reasoning = (
            f"grounded={hall.grounded}; addresses={ans.addresses}; "
            f"trusted_context={'yes' if trusted_context else 'no'}; "
            f"hallucination_reasoning={hall.reasoning}"
        )
        print(f"[quality_check] {reasoning}")

        ledger = append_quality_check(
            state.get("evidence_ledger"),
            name="groundedness",
            verdict=hall.grounded,
            reasoning=hall.reasoning,
        )
        ledger = append_quality_check(
            ledger,
            name="answer_relevance",
            verdict=ans.addresses,
            reasoning="",
        )
        ledger = append_pipeline_step(
            ledger,
            name="quality_check",
            status="success",
            detail={"grounded": hall.grounded, "addresses": ans.addresses},
        )
        return {
            "hallucination_grade": hall.grounded,
            "answer_grade": ans.addresses,
            "quality_reasoning": reasoning,
            "evidence_ledger": ledger,
        }
    return node_quality_check


node_quality_check = make_node_quality_check()

### --------------------------- GENERATE --------------------------- ###
def make_node_generate(chain=generation_chain):
    @traceable
    def node_generate(state, config: RunnableConfig | None = None) -> dict:
        """
        Define the generate node which produces an answer based on the 
        retrieved documents.
        Args:
            state: The current CRAG state containing the question and 
                retrieved documents.
        Returns:
            A dictionary containing:
              - the generated answer
              - the context used for generation
              - the updated evidence ledger after the generation step
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
            chain,
            {
                "question": state["question"],
                "context": context,
                "trusted_context": trusted_context,
            },
            invoke_config,
        ).strip()
        ledger = append_pipeline_step(
            state.get("evidence_ledger"),
            name="generate",
            status="success",
            detail={
                "context_chars": len(context),
                "trusted_context_chars": len(trusted_context),
            },
        )
        return {"answer": answer, "context": context, "evidence_ledger": ledger}
    return node_generate


node_generate = make_node_generate()

### --------------------------- FALLBACK --------------------------- ###
def make_node_fallback(chain=fallback_chain):
    @traceable
    def node_fallback(state, config: RunnableConfig | None = None) -> dict:
        """
        Generate a fallback answer when the knowledge base retrieval and rewrite
        attempts did not produce relevant usable context.
        Args:
            state: The current CRAG state containing the question and any
                rewritten versions.
        Returns:
            A dictionary containing:
              - the fallback answer
              - an empty context
                - the documents used for generation
              - the updated evidence ledger after the fallback step
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
            chain,
            {
                "question": question,
                "rewritten": rewritten,
            },
            invoke_config,
        ).strip()

        ledger = append_pipeline_step(
            state.get("evidence_ledger"),
            name="fallback",
            status="success",
            detail={"rewritten": rewritten},
        )
        return {
            "answer": answer,
            "context": "",
            "documents": state.get("documents", []),
            "evidence_ledger": ledger,
        }
    return node_fallback


node_fallback = make_node_fallback()