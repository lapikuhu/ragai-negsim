"""Isolated CRAG and GraphRAG resources for full-pipeline evaluation."""

from __future__ import annotations
import asyncio
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Any
from langchain_core.documents import Document

# local imports
from app.airag.chunking.chunkers import get_default_embeddings
from app.airag.embeddings.embeddings import choose_embedding_model
from app.airag.evaluation.eval_chunking import prepare_evaluation_chunks
from app.airag.evaluation.eval_models import EvalCorpus
from app.airag.evaluation.rag_eval_engine import (
    CancellationCallback,
    EvaluationResources,
    EvaluationSpecification,
    FullPipelineEvaluator,
    ProgressCallback,
    RagEvaluationCancelled as RagEvaluationCancelled,
    check_cancellation,
    report_progress,
)
from app.airag.evaluation.rag_eval_helpers import tag_chunks_with_evaluation_ids
from app.airag.knowledge_graph.connection import (
    resolve_neo4j_database,
    resolve_neo4j_uri,
)
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
from app.airag.rag_profiles import (
    get_crag_retrieval_mode,
    normalize_rag_profile_config,
)
from app.airag.retrieval.retrievers import (
    make_bm25_retriever,
    make_dense_retriever,
    make_hybrid_retriever,
)
from app.core.config import settings


HIDDEN_CHUNKING_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CRAG_RETRIEVAL_CONTROL_NAMES = (
    "bm25_weight",
    "dense_k",
    "bm25_k",
    "final_top_k",
    "reranker",
    "top_n",
    "max_rewrite_attempts",
)


def _package_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "unknown"


def normalize_evaluation_specification(configuration: Any) -> EvaluationSpecification:
    """
    Map validated user-facing schema names onto internal runtime controls.
    Args:
        configuration: A validated user-facing evaluation configuration object.
    Returns:
        An EvaluationSpecification with internal names and controls for
        runtime evaluation.
    """
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
        retrieval_controls = {
            name: rag.pop(name) for name in CRAG_RETRIEVAL_CONTROL_NAMES
        }
        normalized_retrieval = normalize_rag_profile_config(
            "crag",
            retrieval_controls,
        )
        retrieval = {
            name: normalized_retrieval[name] for name in CRAG_RETRIEVAL_CONTROL_NAMES
        }
        retrieval_mode = get_crag_retrieval_mode(retrieval["bm25_weight"])
        retrieval_embedding_model = rag.pop("retrieval_embedding_model", None)
        if retrieval_mode == "bm25":
            if retrieval_embedding_model is not None:
                raise ValueError(
                    "retrieval_embedding_model is not allowed for BM25-only CRAG"
                )
        elif retrieval_embedding_model is None:
            raise ValueError(
                "retrieval_embedding_model is required for dense and hybrid CRAG"
            )
        else:
            retrieval["retrieval_embedding_model"] = retrieval_embedding_model
        response_pipeline = {
            "reranker": normalized_retrieval["reranker"],
            "top_n": normalized_retrieval["top_n"],
            "max_rewrite_attempts": normalized_retrieval["max_rewrite_attempts"],
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
        retrieval=retrieval if strategy == "crag" else rag,
        k=configuration.metrics.k,
    )


def resolve_chunking_embedding(
    strategy: str
) -> tuple[Any | None, dict[str, Any] | None]:
    """
    Resolve the hidden semantic boundary model and its non-secret identity.
    Args:
        strategy: The chunking strategy, either "semantic" or "hybrid".
    Returns:
        A tuple containing the hidden semantic boundary model (or None) and its non-secret identity (or None).
    """
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
    """
    Create a scoped Neo4j property graph store for a deterministic 
    evaluation run.
    Args:
        run_id: The unique identifier for the evaluation run.
    Returns:
        An instance of ScopedSchemaNeo4jPropertyGraphStore configured for 
        the evaluation run.
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
    Delete and close a deterministic graph generation for restart recovery.
    Args:
        run_id: The unique identifier for the evaluation run.
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
    Create evaluation graph chunks from documents.
    Args:
        chunks: A list of Document objects to be converted into 
            EvalGraphChunk instances.
    Returns:
        A list of EvalGraphChunk instances.
    Raises:
        ValueError: If any document does not have a valid eval_document_id 
        in its metadata.
    """
    document_ids = {chunk.metadata.get("eval_document_id") for chunk in chunks}
    if not all(
        isinstance(document_id, str) and document_id for document_id in document_ids
    ):
        raise ValueError(
            "Evaluation graph chunks must include eval_document_id metadata"
        )
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


def _assign_evaluation_document_chunk_ids(chunks: list[Document]) -> list[Document]:
    """
    Copy tagged chunks with deterministic IDs shared by CRAG retrievers.
    Args:
        chunks: A list of Document objects to be assigned deterministic 
            chunk IDs.
    Returns:
        A list of Document objects with updated metadata containing 
        deterministic chunk IDs.
    """
    return [
        Document(
            page_content=chunk.page_content,
            metadata={**chunk.metadata, "document_chunk_id": chunk_id},
        )
        for chunk_id, chunk in enumerate(chunks, start=1)
    ]


async def _prepare_tagged_chunks(
    specification: EvaluationSpecification,
    corpus: EvalCorpus,
    progress_callback: ProgressCallback | None,
    should_cancel: CancellationCallback | None,
) -> tuple[list[Document], dict[str, Any] | None]:
    """
    Prepare evaluation chunks with deterministic IDs and embedding metadata.
    Args:
        specification: The evaluation specification containing chunking 
            strategy.
        corpus: The evaluation corpus containing documents.
        progress_callback: Optional callback for reporting progress.
        should_cancel: Optional callback for checking cancellation.

    Returns:
        A tuple containing a list of tagged Document objects and optional 
        embedding metadata.
    """
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
    tagged = _assign_evaluation_document_chunk_ids(
        tag_chunks_with_evaluation_ids(chunks, corpus)
    )
    await report_progress(progress_callback, "chunking", 1.0)
    await check_cancellation(should_cancel)
    return tagged, embedding_metadata


class CragEvaluationAdapter:
    """Build isolated dense, BM25, or hybrid resources for one evaluation run."""
    async def prepare(
        self,
        *,
        specification: EvaluationSpecification,
        corpus: EvalCorpus,
        run_id: int,
        progress_callback: ProgressCallback | None,
        should_cancel: CancellationCallback | None,
    ) -> EvaluationResources:
        """
        Prepare evaluation resources for the given evaluation run.
        Args:
            specification: The evaluation specification containing 
                retrieval and chunking settings.
            corpus: The evaluation corpus containing documents.
            run_id: The unique identifier for this evaluation run.
            progress_callback: Optional callback for reporting progress.
            should_cancel: Optional callback for checking cancellation.
        Returns:
            An EvaluationResources object containing the prepared retrievers and embeddings.
        """
        del run_id
        chunks, chunking_embedding = await _prepare_tagged_chunks(
            specification, corpus, progress_callback, should_cancel
        )
        await report_progress(progress_callback, "building_index", 0.0)
        await check_cancellation(should_cancel)
        retrieval = specification.retrieval
        retrieval_mode = get_crag_retrieval_mode(retrieval["bm25_weight"])
        dense_k = int(retrieval["dense_k"])
        bm25_k = int(retrieval["bm25_k"])
        final_top_k = int(retrieval["final_top_k"])
        dense_retriever = None
        bm25_retriever = None
        retrieval_embedding = None
        dependency_versions = {
            "langchain-community": _package_version("langchain-community"),
        }

        if retrieval_mode in {"dense", "hybrid"}:
            model = str(retrieval["retrieval_embedding_model"])
            embeddings, metadata = choose_embedding_model(model)
            retrieval_embedding = {"model": model, **dict(metadata or {})}
            await check_cancellation(should_cancel)
            from langchain_community.vectorstores import FAISS

            store = await asyncio.to_thread(FAISS.from_documents, chunks, embeddings)
            dense_retriever = await asyncio.to_thread(
                make_dense_retriever,
                store,
                k=dense_k,
            )
            dependency_versions["faiss-cpu"] = _package_version("faiss-cpu")
            await check_cancellation(should_cancel)

        if retrieval_mode in {"bm25", "hybrid"}:
            bm25_retriever = await asyncio.to_thread(
                make_bm25_retriever,
                chunks,
                k=bm25_k,
            )
            dependency_versions["rank-bm25"] = _package_version("rank-bm25")
            await check_cancellation(should_cancel)

        retriever = make_hybrid_retriever(
            dense_retriever=dense_retriever,
            bm25_retriever=bm25_retriever,
            bm25_weight=retrieval["bm25_weight"],
            dense_k=dense_k,
            bm25_k=bm25_k,
            final_top_k=final_top_k,
        )
        await report_progress(progress_callback, "building_index", 1.0)
        return EvaluationResources(
            retriever=retriever,
            resolved_metadata={
                "retrieval_mode": retrieval_mode,
                "retrieval_embedding": retrieval_embedding,
                "chunking_embedding": chunking_embedding,
                "fixed_dependency_versions": dependency_versions,
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
    """
    Select the appropriate evaluation adapter based on the specified strategy.
    Args:
        strategy: The evaluation strategy, either "crag" or "graphrag".
    Returns:
        An instance of the corresponding evaluation adapter.
    Raises:
        ValueError: If the specified strategy is unsupported.
    """
    normalized = strategy.strip().lower()
    if normalized == "crag":
        return CragEvaluationAdapter()
    if normalized == "graphrag":
        return GraphRagEvaluationAdapter()
    raise ValueError(f"Unsupported RAG evaluation strategy: {strategy}")


class DefaultRagEvalRuntime:
    """
    Production entry point for a validated typed evaluation configuration.
    """
    def __init__(self, *, pipeline_builder=None, adapter_selector=None) -> None:
        self._evaluator = FullPipelineEvaluator(
            pipeline_builder=pipeline_builder or build_response_pipeline
        )
        self._adapter_selector = adapter_selector or adapter_for_strategy

    async def run(
        self,
        *,
        run_id: int,
        configuration,
        corpus: EvalCorpus,
        progress_callback: ProgressCallback | None = None,
        should_cancel: CancellationCallback | None = None,
    ):
        """
        Run the evaluation using the specified configuration and corpus.
        Args:
            run_id: The unique identifier for this evaluation run.
            configuration: The evaluation configuration.
            corpus: The evaluation corpus containing documents.
            progress_callback: Optional callback for reporting progress.
            should_cancel: Optional callback for checking cancellation.
        Returns:
            The result of the evaluation.
        """
        specification = normalize_evaluation_specification(configuration)
        return await self._evaluator.evaluate(
            specification=specification,
            corpus=corpus,
            adapter=self._adapter_selector(specification.strategy),
            run_id=run_id,
            progress_callback=progress_callback,
            should_cancel=should_cancel,
        )


def create_rag_eval_runtime() -> DefaultRagEvalRuntime:
    return DefaultRagEvalRuntime()
