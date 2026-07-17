"""Isolated CRAG and GraphRAG resources for full-pipeline evaluation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from langchain_core.documents import Document

from app.airag.chunking.chunkers import get_default_embeddings
from app.airag.embeddings.embeddings import choose_embedding_model
from app.airag.evaluation.eval_chunking import prepare_evaluation_chunks
from app.airag.evaluation.eval_models import (
    EvalCorpus,
    EvalQueryResult,
    EvalRunResult,
)
from app.airag.evaluation.rag_eval_engine import (
    CancellationCallback,
    EvaluationResources,
    EvaluationSpecification,
    FullPipelineEvaluator,
    ProgressCallback,
    RagEvaluationCancelled,
    check_cancellation,
    report_progress,
)
from app.airag.evaluation.rag_eval_helpers import (
    calculate_hit_rate_at_k,
    calculate_mrr_at_k,
    create_eval_corpus,
    tag_chunks_with_evaluation_ids,
)
from app.airag.knowledge_graph.connection import resolve_neo4j_database, resolve_neo4j_uri
from app.airag.knowledge_graph.k_graph import (
    build_graph_text_nodes,
    build_property_graph_index,
    create_graph_embedding_model,
    create_graph_llm,
    create_kg_extractors,
)
from app.airag.knowledge_graph.retrieval import ScopedGraphRetriever
from app.airag.knowledge_graph.scoped_schema_store import (
    ScopedSchemaNeo4jPropertyGraphStore,
)
from app.airag.pipeline_factory import build_response_pipeline
from app.core.config import settings


HIDDEN_CHUNKING_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _package_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "unknown"


def normalize_evaluation_specification(configuration: Any) -> EvaluationSpecification:
    """Map validated user-facing schema names onto internal runtime controls."""
    chunking = configuration.chunking.model_dump(mode="python")
    rag = configuration.rag.model_dump(mode="python")
    strategy = rag.pop("strategy")
    component_names = {
        "document_grader": "document_grader",
        "query_rewriter": "rewrite",
        "answer_generator": "generate",
        "hallucination_grader": "hallucination_grader",
        "answer_grader": "answer_grader",
        "fallback_generator": "fallback",
    }
    llm_components = {
        internal: dict(rag.pop(external))
        for external, internal in component_names.items()
    }
    if strategy == "crag":
        response_pipeline = {
            "reranker": rag.pop("reranker"),
            "top_n": rag.pop("top_n"),
            "max_rewrite_attempts": rag.pop("rewrite_limit"),
            "llm_components": llm_components,
        }
    else:
        response_pipeline = {
            "reranker": "none",
            "top_n": rag["evidence_limit"],
            "max_rewrite_attempts": 1,
            "llm_components": llm_components,
        }
        rag["rrf_k"] = rag.pop("rrf_constant")
    chunking_strategy = chunking.pop("strategy")
    return EvaluationSpecification(
        strategy=strategy,
        chunking={"strategy": chunking_strategy, "config": chunking},
        response_pipeline=response_pipeline,
        retrieval=rag,
        k=configuration.metrics.k,
    )


def resolve_chunking_embedding(strategy: str) -> tuple[Any | None, dict[str, Any] | None]:
    """Resolve the hidden semantic boundary model and its non-secret identity."""
    if strategy not in {"semantic", "hybrid"}:
        return None, None
    return get_default_embeddings(), {
        "provider": "huggingface",
        "model": HIDDEN_CHUNKING_EMBEDDING_MODEL,
    }


@dataclass(frozen=True)
class EvalGraphChunk:
    id: int
    content: str
    chunk_metadata: dict
    raw_document_id: int
    chunking_profile_id: int | None
    chunk_index: int


def _evaluation_graph_scope(run_id: int) -> tuple[int, str]:
    if run_id < 1:
        raise ValueError("RAG evaluation run_id must be positive")
    return -run_id, "rag-eval"


def _create_evaluation_graph_store(run_id: int) -> ScopedSchemaNeo4jPropertyGraphStore:
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
    """Delete and close a deterministic graph generation for restart recovery."""
    store = _create_evaluation_graph_store(run_id)
    try:
        await asyncio.to_thread(store.delete_generation)
    finally:
        store.close()


def _make_eval_graph_chunks(chunks: list[Document]) -> list[EvalGraphChunk]:
    document_ids = {chunk.metadata.get("eval_document_id") for chunk in chunks}
    if not all(
        isinstance(document_id, str) and document_id for document_id in document_ids
    ):
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


async def _prepare_tagged_chunks(
    specification: EvaluationSpecification,
    corpus: EvalCorpus,
    progress_callback: ProgressCallback | None,
    should_cancel: CancellationCallback | None,
) -> tuple[list[Document], dict[str, Any] | None]:
    await check_cancellation(should_cancel)
    await report_progress(progress_callback, "chunking", 0.0)
    strategy = str(specification.chunking["strategy"])
    embeddings, embedding_metadata = resolve_chunking_embedding(strategy)
    chunks = await asyncio.to_thread(
        prepare_evaluation_chunks,
        corpus.documents,
        dict(specification.chunking),
        embeddings=embeddings,
    )
    tagged = tag_chunks_with_evaluation_ids(chunks, corpus)
    await report_progress(progress_callback, "chunking", 1.0)
    await check_cancellation(should_cancel)
    return tagged, embedding_metadata


class CragEvaluationAdapter:
    """Build an in-memory FAISS retriever for one evaluation run."""

    async def prepare(
        self,
        *,
        specification: EvaluationSpecification,
        corpus: EvalCorpus,
        run_id: int,
        progress_callback: ProgressCallback | None,
        should_cancel: CancellationCallback | None,
    ) -> EvaluationResources:
        del run_id
        chunks, chunking_embedding = await _prepare_tagged_chunks(
            specification, corpus, progress_callback, should_cancel
        )
        await report_progress(progress_callback, "building_index", 0.0)
        await check_cancellation(should_cancel)
        model = str(specification.retrieval["retrieval_embedding_model"])
        embeddings, metadata = choose_embedding_model(model)
        await check_cancellation(should_cancel)
        from langchain_community.vectorstores import FAISS

        store = await asyncio.to_thread(FAISS.from_documents, chunks, embeddings)
        await check_cancellation(should_cancel)
        top_k = int(specification.retrieval["top_k"])
        retriever = store.as_retriever(search_kwargs={"k": top_k})
        await report_progress(progress_callback, "building_index", 1.0)
        return EvaluationResources(
            retriever=retriever,
            resolved_metadata={
                "retrieval_embedding": {"model": model, **dict(metadata or {})},
                "chunking_embedding": chunking_embedding,
                "fixed_dependency_versions": {
                    "faiss-cpu": _package_version("faiss-cpu"),
                    "langchain-community": _package_version("langchain-community"),
                },
            },
            cleanup=lambda: None,
        )


class GraphRagEvaluationAdapter:
    """Build and own one deterministic run-scoped temporary property graph."""

    async def prepare(
        self,
        *,
        specification: EvaluationSpecification,
        corpus: EvalCorpus,
        run_id: int,
        progress_callback: ProgressCallback | None,
        should_cancel: CancellationCallback | None,
    ) -> EvaluationResources:
        chunks, chunking_embedding = await _prepare_tagged_chunks(
            specification, corpus, progress_callback, should_cancel
        )
        graph_id, generation = _evaluation_graph_scope(run_id)
        store = _create_evaluation_graph_store(run_id)

        async def cleanup() -> None:
            try:
                await asyncio.to_thread(store.delete_generation)
            finally:
                store.close()

        try:
            await asyncio.to_thread(store.delete_generation)
            await report_progress(progress_callback, "building_graph", 0.0)
            await check_cancellation(should_cancel)
            extraction = dict(specification.retrieval["extraction_llm"])
            graph_config = {
                "llm_provider": extraction["provider"],
                "llm_model": extraction["model"],
                "embedding_model": specification.retrieval["graph_embedding_model"],
                "max_paths_per_chunk": specification.retrieval["max_paths_per_chunk"],
                # Schema extraction is corpus-specific and meaningless for the generic
                # evaluation suite; evaluation accepts no schema or implicit extractor.
                "extractors": ["simple"],
            }
            llm = create_graph_llm(graph_config)
            await check_cancellation(should_cancel)
            embedding_model = create_graph_embedding_model(graph_config)
            await check_cancellation(should_cancel)
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
            await check_cancellation(should_cancel)
            retriever = ScopedGraphRetriever(
                graph_store=store,
                graph_id=graph_id,
                generation=generation,
                embedding_model=embedding_model,
                llm=llm,
                chunks_by_id={chunk.id: chunk for chunk in graph_chunks},
                mode=str(specification.retrieval["retrieval_mode"]),
                evidence_limit=int(specification.retrieval["evidence_limit"]),
                traversal_depth=int(specification.retrieval["traversal_depth"]),
                rrf_k=int(specification.retrieval["rrf_k"]),
            )
            await report_progress(progress_callback, "building_graph", 1.0)
            return EvaluationResources(
                retriever=retriever,
                resolved_metadata={
                    "extraction_llm": extraction,
                    "graph_embedding": {
                        "model": specification.retrieval["graph_embedding_model"]
                    },
                    "chunking_embedding": chunking_embedding,
                    "extractor": {
                        "implementation": "simple",
                        "max_paths_per_chunk": specification.retrieval[
                            "max_paths_per_chunk"
                        ],
                    },
                    "fixed_dependency_versions": {
                        "llama-index-core": _package_version("llama-index-core"),
                    },
                },
                cleanup=cleanup,
            )
        except BaseException:
            await cleanup()
            raise


def adapter_for_strategy(strategy: str):
    normalized = strategy.strip().lower()
    if normalized == "crag":
        return CragEvaluationAdapter()
    if normalized == "graphrag":
        return GraphRagEvaluationAdapter()
    raise ValueError(f"Unsupported RAG evaluation strategy: {strategy}")


class DefaultRagEvalRuntime:
    """Compatibility façade while persistence adopts typed configurations."""

    def __init__(self) -> None:
        self._evaluator = FullPipelineEvaluator(
            pipeline_builder=build_response_pipeline
        )

    async def run(
        self,
        *,
        run_id: int,
        rag_snapshot: dict,
        chunking_snapshot: dict,
        retrieval_config_snapshot: dict,
        k: int,
        stage_callback=None,
        should_cancel: CancellationCallback | None = None,
    ) -> EvalRunResult:
        strategy = str(rag_snapshot["strategy"])
        rag_config = dict(rag_snapshot.get("config") or {})
        components = rag_config.get("llm_components") or {}
        response_pipeline = {
            **rag_config,
            "llm_components": components,
            "max_rewrite_attempts": rag_config.get(
                "max_rewrite_attempts",
                rag_config.get("rewrite_limit", 2 if strategy == "crag" else 1),
            ),
        }
        if strategy == "crag":
            retrieval = {
                "retrieval_embedding_model": retrieval_config_snapshot[
                    "embedding_model"
                ],
                "top_k": int(rag_config.get("top_k", k)),
            }
        else:
            graph_build = dict(retrieval_config_snapshot["graph_build"])
            retrieval = {
                "extraction_llm": {
                    "provider": graph_build["llm_provider"],
                    "model": graph_build["llm_model"],
                },
                "graph_embedding_model": retrieval_config_snapshot["embedding_model"],
                "max_paths_per_chunk": graph_build.get("max_paths_per_chunk", 10),
                "retrieval_mode": rag_config.get("retrieval_mode", "semantic"),
                "evidence_limit": rag_config.get("evidence_limit", k),
                "traversal_depth": rag_config.get("traversal_depth", 2),
                "rrf_k": rag_config.get("rrf_k", rag_config.get("rrf_constant", 60)),
            }
        specification = EvaluationSpecification(
            strategy=strategy,
            chunking={
                "strategy": chunking_snapshot["strategy"],
                "config": dict(chunking_snapshot.get("config") or {}),
            },
            response_pipeline=response_pipeline,
            retrieval=retrieval,
            k=k,
        )
        corpus = create_eval_corpus()
        last_stage = None

        async def forward_progress(update):
            nonlocal last_stage
            if stage_callback is not None and update.stage != last_stage:
                last_stage = update.stage
                await stage_callback(update.stage)

        evaluated = await self._evaluator.evaluate(
            specification=specification,
            corpus=corpus,
            adapter=adapter_for_strategy(strategy),
            run_id=run_id,
            progress_callback=forward_progress,
            should_cancel=should_cancel,
        )
        query_results = []
        for example, row in zip(corpus.examples, evaluated.results, strict=True):
            retrieved_ids = tuple(
                document.evaluation_ids for document in row.ranked_documents
            )
            first_rank = next(
                (
                    rank
                    for rank, ids in enumerate(retrieved_ids[:k], start=1)
                    if example.evaluation_id in ids
                ),
                None,
            )
            query_results.append(
                EvalQueryResult(
                    evaluation_id=row.evaluation_id,
                    query=row.query,
                    answer=row.answer,
                    reference=row.reference_answer,
                    retrieved_contexts=row.contexts,
                    retrieved_evaluation_ids=retrieved_ids,
                    first_relevant_rank=first_rank,
                    hit_at_k=first_rank is not None,
                    reciprocal_rank_at_k=(
                        0.0 if first_rank is None else 1.0 / first_rank
                    ),
                )
            )
        return EvalRunResult(
            k=k,
            results=tuple(query_results),
            hit_rate_at_k=calculate_hit_rate_at_k(query_results),
            mrr_at_k=calculate_mrr_at_k(query_results),
        )


def create_rag_eval_runtime() -> DefaultRagEvalRuntime:
    return DefaultRagEvalRuntime()
