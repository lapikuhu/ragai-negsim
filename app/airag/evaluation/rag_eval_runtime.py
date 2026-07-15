"""Isolated runtime boundary for persisted RAG evaluation runs.

The service depends on this small interface so orchestration can be tested without
FAISS, providers, or Neo4j.  Production CRAG evaluation only creates in-memory
resources; GraphRAG deliberately refuses to borrow a profile's live graph.
"""
from __future__ import annotations

from typing import Protocol

from langchain_core.documents import Document

from app.airag.chunking.chunkers import chunk_document_list_recursive
from app.airag.evaluation.rag_eval_helpers import (
    create_eval_corpus,
    make_invoke_runner,
    run_eval_suite,
    tag_chunks_with_evaluation_ids,
)
from app.airag.evaluation.eval_models import EvalQueryResult, EvalRunResult
from app.airag.embeddings.embeddings import choose_embedding_model


class RagEvalRuntime(Protocol):
    async def run(self, *, rag_snapshot: dict, chunking_snapshot: dict, k: int) -> EvalRunResult: ...


class DefaultRagEvalRuntime:
    async def run(self, *, rag_snapshot: dict, chunking_snapshot: dict, k: int) -> EvalRunResult:
        strategy = rag_snapshot.get("strategy")
        if strategy == "graphrag":
            raise ValueError(
                "GraphRAG evaluation requires an isolated scoped graph runtime; live graph reuse is prohibited"
            )
        if strategy != "crag":
            raise ValueError(f"Unsupported RAG evaluation strategy: {strategy}")

        corpus = create_eval_corpus()
        config = chunking_snapshot.get("config", {})
        if chunking_snapshot.get("strategy") != "recursive":
            raise ValueError("The default evaluation runtime currently supports recursive chunking only")
        chunks = chunk_document_list_recursive(
            list(corpus.documents),
            chunk_size=config.get("chunk_size", 1000),
            chunk_overlap=config.get("chunk_overlap", 200),
            separators=config.get("separators"),
        )
        chunks = tag_chunks_with_evaluation_ids(chunks, corpus)
        embeddings, _ = choose_embedding_model("text-embedding-3-small")
        from langchain_community.vectorstores import FAISS

        store = FAISS.from_documents(chunks, embeddings)
        top_k = int(rag_snapshot.get("config", {}).get("top_k", k))
        runner = make_invoke_runner(store.as_retriever(search_kwargs={"k": top_k}))
        retrieval_result = run_eval_suite(corpus, runner, k=k)
        # Ragas requires an answer.  This retrieval-domain evaluation uses the
        # retrieved evidence as the minimal grounded answer rather than
        # introducing a separate answer-generation profile.
        results = tuple(
            EvalQueryResult(
                evaluation_id=row.evaluation_id,
                query=row.query,
                answer="\n\n".join(row.retrieved_contexts) or None,
                reference=row.reference,
                retrieved_contexts=row.retrieved_contexts,
                retrieved_evaluation_ids=row.retrieved_evaluation_ids,
                first_relevant_rank=row.first_relevant_rank,
                hit_at_k=row.hit_at_k,
                reciprocal_rank_at_k=row.reciprocal_rank_at_k,
            )
            for row in retrieval_result.results
        )
        return EvalRunResult(
            k=retrieval_result.k,
            results=results,
            hit_rate_at_k=retrieval_result.hit_rate_at_k,
            mrr_at_k=retrieval_result.mrr_at_k,
        )


def create_rag_eval_runtime() -> RagEvalRuntime:
    return DefaultRagEvalRuntime()
