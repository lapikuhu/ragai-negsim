"""Isolated runtime boundary for persisted RAG evaluation runs.

The service depends on this small interface so orchestration can be tested without
FAISS, providers, or Neo4j.  Production CRAG evaluation only creates in-memory
resources; GraphRAG deliberately refuses to borrow a profile's live graph.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from collections.abc import Awaitable, Callable
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
from app.airag.knowledge_graph.connection import resolve_neo4j_database, resolve_neo4j_uri
from app.airag.knowledge_graph.k_graph import (
    build_graph_text_nodes,
    build_property_graph_index,
    create_graph_embedding_model,
    create_graph_llm,
    create_kg_extractors,
)
from app.airag.knowledge_graph.retrieval import ScopedGraphRetriever
from app.airag.knowledge_graph.scoped_schema_store import ScopedSchemaNeo4jPropertyGraphStore
from app.core.config import settings


RagEvalStageCallback = Callable[[str], Awaitable[None]]


class RagEvalRuntime(Protocol):
    async def run(
        self,
        *,
        run_id: int,
        rag_snapshot: dict,
        chunking_snapshot: dict,
        retrieval_config_snapshot: dict,
        k: int,
        stage_callback: RagEvalStageCallback | None = None,
    ) -> EvalRunResult: ...


@dataclass(frozen=True)
class EvalGraphChunk:
    id: int
    content: str
    chunk_metadata: dict
    raw_document_id: int
    chunking_profile_id: int | None
    chunk_index: int


def _evaluation_graph_scope(run_id: int) -> tuple[int, str]:
    """
    Get the evaluation graph scope for a given run ID.
    Args:
        run_id: The unique identifier for the RAG evaluation run.
    Returns:
        A tuple containing the graph ID and generation string.
    Raises:
        ValueError: If the run_id is not positive.
    """
    if run_id < 1:
        raise ValueError("RAG evaluation run_id must be positive")
    return -run_id, "rag-eval"


def _create_evaluation_graph_store(run_id: int) -> ScopedSchemaNeo4jPropertyGraphStore:
    """
    Create the evaluation graph store for a given run ID.
    Args:
        run_id: The unique identifier for the RAG evaluation run.
    Returns:
        ScopedSchemaNeo4jPropertyGraphStore: The evaluation graph store 
        instance.
    """
    graph_id, generation = _evaluation_graph_scope(run_id)
    return ScopedSchemaNeo4jPropertyGraphStore(
        graph_id=graph_id,
        generation=generation,
        schema_refresh_enabled=False,
        username=settings.NEO4J_USERNAME,
        password=settings.NEO4J_PASSWORD,
        url=resolve_neo4j_uri(settings.NEO4J_URI),
        database=resolve_neo4j_database(settings.NEO4J_DATABASE),
    )


async def cleanup_rag_eval_graph_scope(run_id: int) -> None:
    """
    Delete and close the deterministic temporary graph scope for a run.
    Args:
        run_id: The unique identifier for the RAG evaluation run.
    Returns:
        None
    """
    store = _create_evaluation_graph_store(run_id)
    try:
        await asyncio.to_thread(store.delete_generation)
    finally:
        store.close()


def _make_eval_graph_chunks(chunks: list[Document]) -> list[EvalGraphChunk]:
    """
    Create evaluation graph chunks from a list of documents.
    Args:
        chunks: A list of Document instances to be converted into 
            evaluation graph chunks.
    Returns:
        A list of EvalGraphChunk instances.
    Raises:
        ValueError: If any document is missing the required 
        eval_document_id metadata.
    """
    document_ids = {
        chunk.metadata.get("eval_document_id")
        for chunk in chunks
    }
    if not all(isinstance(document_id, str) and document_id for document_id in document_ids):
        raise ValueError("Evaluation graph chunks must include eval_document_id metadata")
    raw_document_ids = {
        document_id: index
        for index, document_id in enumerate(sorted(document_ids), start=1)
    }
    return [
        EvalGraphChunk(
            id=index,
            content=chunk.page_content,
            chunk_metadata=dict(chunk.metadata),
            raw_document_id=raw_document_ids[chunk.metadata["eval_document_id"]],
            chunking_profile_id=None,
            chunk_index=int(chunk.metadata.get("chunk_index", index - 1)),
        )
        for index, chunk in enumerate(chunks, start=1)
    ]


class DefaultRagEvalRuntime:
    async def run(
        self,
        *,
        run_id: int,
        rag_snapshot: dict,
        chunking_snapshot: dict,
        retrieval_config_snapshot: dict,
        k: int,
        stage_callback: RagEvalStageCallback | None = None,
    ) -> EvalRunResult:
        """
        Generate an evaluation run result for the given RAG evaluation run.
        Args:
            run_id: The unique identifier for the RAG evaluation run.
            rag_snapshot: The RAG snapshot configuration.
            chunking_snapshot: The chunking snapshot configuration.
            retrieval_config_snapshot: The retrieval configuration snapshot.
            k: The number of top retrieved results to consider.
            stage_callback: An optional callback for reporting evaluation 
                stages.
        Returns:
            An EvalRunResult instance containing the evaluation results.
        Raises:
            ValueError: If the RAG evaluation strategy is unsupported.
        """
        strategy = rag_snapshot.get("strategy")
        if strategy not in {"crag", "graphrag"}:
            raise ValueError(f"Unsupported RAG evaluation strategy: {strategy}")

        await self._report_stage(stage_callback, "chunking")
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
        if strategy == "crag":
            await self._report_stage(stage_callback, "retrieving")
            retrieval_result = await asyncio.to_thread(
                self._run_crag,
                corpus=corpus,
                chunks=chunks,
                rag_snapshot=rag_snapshot,
                retrieval_config_snapshot=retrieval_config_snapshot,
                k=k,
            )
        else:
            retrieval_result = await self._run_graphrag(
                run_id=run_id,
                corpus=corpus,
                chunks=chunks,
                rag_snapshot=rag_snapshot,
                retrieval_config_snapshot=retrieval_config_snapshot,
                k=k,
                stage_callback=stage_callback,
            )
        results = tuple(
            EvalQueryResult(
                evaluation_id=row.evaluation_id,
                query=row.query,
                answer=row.answer,
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

    @staticmethod
    async def _report_stage(stage_callback: RagEvalStageCallback | None, stage: str) -> None:
        """
        Report the current stage of the RAG evaluation.
        Args:
            stage_callback: The callback to report the stage to.
            stage: The name of the current stage.
        """
        if stage_callback is not None:
            await stage_callback(stage)

    @staticmethod
    def _run_crag(*, corpus,
                  chunks,
                  rag_snapshot: dict,
                  retrieval_config_snapshot: dict,
                  k: int) -> EvalRunResult:
        """
        Run a CRAG evaluation using FAISS as the retrieval backend.
        Args:
            corpus: The evaluation corpus.
            chunks: The list of document chunks to index.
            rag_snapshot: The RAG evaluation snapshot containing configuration.
            retrieval_config_snapshot: The retrieval configuration snapshot.
            k: The number of top results to retrieve.
        Returns:
            An EvalRunResult containing the evaluation results.
        """
        embedding_model = retrieval_config_snapshot.get("embedding_model")
        if not isinstance(embedding_model, str) or not embedding_model.strip():
            raise ValueError("RAG evaluation retrieval config requires an embedding_model")
        embeddings, _ = choose_embedding_model(embedding_model)
        from langchain_community.vectorstores import FAISS

        store = FAISS.from_documents(chunks, embeddings)
        top_k = int(rag_snapshot.get("config", {}).get("top_k", k))
        runner = make_invoke_runner(store.as_retriever(search_kwargs={"k": top_k}))
        return run_eval_suite(corpus, runner, k=k)

    @staticmethod
    async def _run_graphrag(
        *,
        run_id: int,
        corpus,
        chunks: list[Document],
        rag_snapshot: dict,
        retrieval_config_snapshot: dict,
        k: int,
        stage_callback: RagEvalStageCallback | None,
    ) -> EvalRunResult:
        """
        Run a GraphRAG evaluation using a property graph as the retrieval
        backend.
        Args:
            run_id: The unique identifier for this evaluation run.
            corpus: The evaluation corpus.
            chunks: The list of document chunks to index.
            rag_snapshot: The RAG evaluation snapshot containing configuration.
            retrieval_config_snapshot: The retrieval configuration snapshot.
            k: The number of top results to retrieve.
            stage_callback: An optional callback for reporting
                evaluation stages.
        Returns:
            An EvalRunResult containing the evaluation results.
        """
        graph_build = retrieval_config_snapshot.get("graph_build")
        if not isinstance(graph_build, dict):
            raise ValueError("GraphRAG evaluation retrieval config requires graph_build")
        graph_config = {
            **graph_build,
            "embedding_model": retrieval_config_snapshot.get("embedding_model"),
            "extractors": ["simple"],
        }
        graph_id, generation = _evaluation_graph_scope(run_id)
        store = _create_evaluation_graph_store(run_id)
        try:
            await asyncio.to_thread(store.delete_generation)
            await DefaultRagEvalRuntime._report_stage(stage_callback, "building_graph")
            llm = create_graph_llm(graph_config)
            embedding_model = create_graph_embedding_model(graph_config)
            extractors = create_kg_extractors(graph_config, llm=llm)
            graph_chunks = _make_eval_graph_chunks(chunks)
            nodes = build_graph_text_nodes(
                graph_chunks,
                graph_id=graph_id,
                generation=generation,
                corpus_index_id=graph_id,
            )
            await asyncio.to_thread(
                build_property_graph_index,
                nodes=nodes,
                graph_store=store,
                llm=llm,
                embedding_model=embedding_model,
                kg_extractors=extractors,
            )
            config = rag_snapshot.get("config", {})
            retriever = ScopedGraphRetriever(
                graph_store=store,
                graph_id=graph_id,
                generation=generation,
                embedding_model=embedding_model,
                llm=llm,
                chunks_by_id={chunk.id: chunk for chunk in graph_chunks},
                mode=config.get("retrieval_mode", "semantic"),
                evidence_limit=int(config.get("evidence_limit", k)),
                traversal_depth=int(config.get("traversal_depth", 2)),
                rrf_k=int(config.get("rrf_k", 60)),
            )
            await DefaultRagEvalRuntime._report_stage(stage_callback, "retrieving")
            return await asyncio.to_thread(
                run_eval_suite,
                corpus,
                make_invoke_runner(retriever),
                k=k,
            )
        finally:
            await asyncio.to_thread(store.delete_generation)
            store.close()


def create_rag_eval_runtime() -> RagEvalRuntime:
    return DefaultRagEvalRuntime()
