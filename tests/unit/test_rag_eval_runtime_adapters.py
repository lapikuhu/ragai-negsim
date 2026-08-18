from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from app.airag.evaluation.eval_models import EvalCorpus, EvalExample
from app.airag.evaluation.rag_eval_engine import EvaluationSpecification
from app.airag.evaluation import rag_eval_runtime


COMPONENTS = {
    "document_grader": {"provider": "openai", "model": "doc"},
    "rewrite": {"provider": "openai", "model": "rewrite"},
    "generate": {"provider": "openai", "model": "generate"},
    "hallucination_grader": {"provider": "openai", "model": "hall"},
    "answer_grader": {"provider": "openai", "model": "answer"},
    "fallback": {"provider": "openai", "model": "fallback"},
}


def _corpus() -> EvalCorpus:
    return EvalCorpus(
        documents=(
            Document(
                page_content="support",
                metadata={"eval_document_id": "synth_doc_1"},
            ),
        ),
        eval_documents=(),
        support_spans=(),
        examples=(EvalExample("example-1", "Question?", "Reference"),),
        suite_version="suite-v2",
        suite_content_hash="hash",
    )


def _spec(
    strategy: str,
    *,
    bm25_weight: float = 0.0,
) -> EvaluationSpecification:
    retrieval = (
        {
            "retrieval_embedding_model": "retrieval-embedding",
            "bm25_weight": bm25_weight,
            "dense_k": 4,
            "bm25_k": 5,
            "final_top_k": 3,
        }
        if strategy == "crag"
        else {
            "extraction_llm": {"provider": "openai", "model": "extract"},
            "graph_embedding_model": "graph-embedding",
            "max_paths_per_chunk": 7,
            "retrieval_mode": "hybrid",
            "evidence_limit": 5,
            "traversal_depth": 3,
            "rrf_k": 71,
        }
    )
    return EvaluationSpecification(
        strategy=strategy,
        chunking={"strategy": "semantic", "config": {}},
        response_pipeline={
            "reranker": "none",
            "top_n": 4,
            "max_rewrite_attempts": 2,
            "llm_components": COMPONENTS,
        },
        retrieval=retrieval,
        k=3,
    )


def test_configuration_boundary_maps_user_facing_component_names():
    configuration = SimpleNamespace(
        chunking=SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "strategy": "recursive",
                "chunk_size": 100,
                "chunk_overlap": 0,
                "separators": ["\n", ""],
            }
        ),
        rag=SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "strategy": "crag",
                "retrieval_embedding_model": "text-embedding-3-small",
                "bm25_weight": 0.25,
                "dense_k": 5,
                "bm25_k": 6,
                "final_top_k": 4,
                "reranker": "none",
                "top_n": 4,
                "max_rewrite_attempts": 3,
                "document_grader": {"provider": "openai", "model": "doc"},
                "query_rewriter": {"provider": "openai", "model": "rewrite"},
                "answer_generator": {"provider": "openai", "model": "generate"},
                "hallucination_grader": {"provider": "openai", "model": "hall"},
                "answer_grader": {"provider": "openai", "model": "answer"},
                "fallback_generator": {"provider": "openai", "model": "fallback"},
            }
        ),
        metrics=SimpleNamespace(k=3),
    )

    specification = rag_eval_runtime.normalize_evaluation_specification(configuration)

    assert specification.response_pipeline["max_rewrite_attempts"] == 3
    assert specification.response_pipeline["llm_components"] == COMPONENTS
    assert specification.retrieval["retrieval_embedding_model"] == (
        "text-embedding-3-small"
    )
    assert specification.retrieval == {
        "bm25_weight": 0.25,
        "dense_k": 5,
        "bm25_k": 6,
        "final_top_k": 4,
        "reranker": "none",
        "top_n": 4,
        "max_rewrite_attempts": 3,
        "retrieval_embedding_model": "text-embedding-3-small",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bm25_weight", "expected_mode", "expects_dense", "expects_bm25"),
    [
        (0.0, "dense", True, False),
        (1.0, "bm25", False, True),
        (0.4, "hybrid", True, True),
    ],
)
async def test_crag_adapter_builds_only_mode_resources_with_stable_chunk_ids(
    monkeypatch,
    bm25_weight,
    expected_mode,
    expects_dense,
    expects_bm25,
):
    captured = {"thread_calls": []}
    tagged = [
        Document(
            page_content="first support",
            metadata={
                "eval_document_id": "synth_doc_1",
                "evaluation_ids": ["example-1"],
            },
        ),
        Document(
            page_content="second support",
            metadata={
                "eval_document_id": "synth_doc_1",
                "evaluation_ids": ["example-1"],
            },
        ),
    ]

    class Store:
        @classmethod
        def from_documents(cls, chunks, embeddings):
            captured["faiss_chunks"] = chunks
            captured["embeddings"] = embeddings
            return cls()

    def prepare_chunks(_documents, _config, **kwargs):
        captured["chunk_kwargs"] = kwargs
        return tagged

    monkeypatch.setattr(
        rag_eval_runtime,
        "prepare_evaluation_chunks",
        prepare_chunks,
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "tag_chunks_with_evaluation_ids",
        lambda _chunks, _corpus: tagged,
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "resolve_chunking_embedding",
        lambda strategy: ("chunk-embeddings", {"model": f"hidden-{strategy}"}),
    )
    def create_embeddings(model, corpus):
        captured["embedding_request"] = (model, corpus.suite_content_hash)
        return (
            "retrieval-embeddings",
            {"model": model, "provider": "fake", "dimensionality": 2},
            {"enabled": False, "hits": 0},
        )

    monkeypatch.setattr(
        rag_eval_runtime,
        "create_evaluation_embeddings",
        create_embeddings,
    )

    def make_dense(store, *, k):
        captured["dense"] = (store, k)
        return "dense"

    def make_bm25(documents, *, k):
        captured["bm25"] = (documents, k)
        return "bm25"

    def make_hybrid(**kwargs):
        captured["hybrid"] = kwargs
        return "hybrid"

    monkeypatch.setattr(
        rag_eval_runtime, "make_dense_retriever", make_dense, raising=False
    )
    monkeypatch.setattr(
        rag_eval_runtime, "make_bm25_retriever", make_bm25, raising=False
    )
    monkeypatch.setattr(
        rag_eval_runtime, "make_hybrid_retriever", make_hybrid, raising=False
    )

    async def run_in_thread(function, *args, **kwargs):
        captured["thread_calls"].append(function)
        return function(*args, **kwargs)

    monkeypatch.setattr(rag_eval_runtime.asyncio, "to_thread", run_in_thread)
    monkeypatch.setitem(
        __import__("sys").modules,
        "langchain_community.vectorstores",
        SimpleNamespace(FAISS=Store),
    )

    progress = []
    resources = await rag_eval_runtime.CragEvaluationAdapter().prepare(
        specification=_spec("crag", bm25_weight=bm25_weight),
        corpus=_corpus(),
        run_id=11,
        progress_callback=progress.append,
        should_cancel=None,
    )

    assert resources.retriever == "hybrid"
    assert captured["chunk_kwargs"]["embeddings"] == "chunk-embeddings"
    assert ("dense" in captured) is expects_dense
    assert ("bm25" in captured) is expects_bm25
    assert ("faiss_chunks" in captured) is expects_dense
    if expects_dense:
        assert captured["embeddings"] == "retrieval-embeddings"
        assert captured["embedding_request"] == ("retrieval-embedding", "hash")
        assert [
            chunk.metadata["document_chunk_id"] for chunk in captured["faiss_chunks"]
        ] == [1, 2]
        assert captured["dense"][1] == 4
        assert resources.resolved_metadata["retrieval_embedding"]["model"] == (
            "retrieval-embedding"
        )
        assert resources.resolved_metadata["embedding_cache"] == {
            "enabled": False,
            "hits": 0,
        }
    else:
        assert "embeddings" not in captured
        assert resources.resolved_metadata["retrieval_embedding"] is None
        assert "embedding_cache" not in resources.resolved_metadata
    if expects_bm25:
        assert [
            chunk.metadata["document_chunk_id"] for chunk in captured["bm25"][0]
        ] == [
            1,
            2,
        ]
        assert captured["bm25"][1] == 5
    assert captured["hybrid"] == {
        "dense_retriever": "dense" if expects_dense else None,
        "bm25_retriever": "bm25" if expects_bm25 else None,
        "bm25_weight": bm25_weight,
        "dense_k": 4,
        "bm25_k": 5,
        "final_top_k": 3,
    }
    assert resources.resolved_metadata["retrieval_mode"] == expected_mode
    assert resources.resolved_metadata["chunking_embedding"] == {
        "model": "hidden-semantic"
    }
    dependency_versions = resources.resolved_metadata["fixed_dependency_versions"]
    assert ("faiss-cpu" in dependency_versions) is expects_dense
    assert ("rank-bm25" in dependency_versions) is expects_bm25
    assert [(item.stage, item.progress) for item in progress] == [
        ("chunking", 0.0),
        ("chunking", 1.0),
        ("building_index", 0.0),
        ("building_index", 1.0),
    ]


@pytest.mark.asyncio
async def test_graphrag_adapter_forces_simple_scope_controls_and_cleanup(monkeypatch):
    captured = {"events": []}
    tagged = Document(
        page_content="support",
        metadata={
            "eval_document_id": "synth_doc_1",
            "start_index": 0,
            "chunk_index": 0,
            "evaluation_ids": ["example-1"],
        },
    )

    class Store:
        def delete_generation(self):
            captured["events"].append("delete")

        def close(self):
            captured["events"].append("close")

    class Retriever:
        def __init__(self, **kwargs):
            captured["retriever"] = kwargs

    monkeypatch.setattr(
        rag_eval_runtime, "_create_evaluation_graph_store", lambda _run_id: Store()
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "prepare_evaluation_chunks",
        lambda *_args, **_kwargs: [tagged],
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "tag_chunks_with_evaluation_ids",
        lambda _chunks, _corpus: [tagged],
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "resolve_chunking_embedding",
        lambda _strategy: ("chunk-embeddings", {"model": "hidden-semantic"}),
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "create_graph_llm",
        lambda config: captured.setdefault("llm_config", config) or "llm",
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "create_evaluation_embeddings",
        lambda model, corpus: (
            "cached-langchain-embedding",
            {"model": model, "provider": "fake", "dimensionality": 2},
            {"enabled": True, "hits": 0},
        ),
    )

    def create_graph_embedding(config, *, langchain_embedding_model):
        captured["embedding_config"] = config
        captured["langchain_embedding_model"] = langchain_embedding_model
        return "embedding"

    monkeypatch.setattr(
        rag_eval_runtime,
        "create_graph_embedding_model",
        create_graph_embedding,
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "create_kg_extractors",
        lambda config, *, llm: captured.setdefault("extractor_config", config)
        and ["simple"],
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "build_property_graph_index",
        lambda **kwargs: captured.setdefault("build", kwargs),
    )
    monkeypatch.setattr(rag_eval_runtime, "ScopedGraphRetriever", Retriever)

    resources = await rag_eval_runtime.GraphRagEvaluationAdapter().prepare(
        specification=_spec("graphrag"),
        corpus=_corpus(),
        run_id=12,
        progress_callback=None,
        should_cancel=None,
    )
    await resources.cleanup()

    assert captured["events"] == ["delete", "delete", "close"]
    assert captured["extractor_config"]["extractors"] == ["simple"]
    assert captured["langchain_embedding_model"] == "cached-langchain-embedding"
    assert captured["retriever"]["graph_id"] == -12
    assert captured["retriever"]["generation"] == "rag-eval"
    assert captured["retriever"]["mode"] == "hybrid"
    assert captured["retriever"]["evidence_limit"] == 5
    assert captured["retriever"]["traversal_depth"] == 3
    assert captured["retriever"]["rrf_k"] == 71
    assert resources.resolved_metadata["extractor"] == {
        "implementation": "simple",
        "max_paths_per_chunk": 7,
    }
    assert resources.resolved_metadata["embedding_cache"] == {
        "enabled": True,
        "hits": 0,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["build", "cancel"])
async def test_graphrag_adapter_cleans_scope_on_build_failure_or_cancellation(
    monkeypatch, failure
):
    events = []
    tagged = Document(
        page_content="support",
        metadata={"eval_document_id": "synth_doc_1", "start_index": 0},
    )

    class Store:
        def delete_generation(self):
            events.append("delete")

        def close(self):
            events.append("close")

    monkeypatch.setattr(
        rag_eval_runtime, "_create_evaluation_graph_store", lambda _run_id: Store()
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "prepare_evaluation_chunks",
        lambda *_args, **_kwargs: [tagged],
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "tag_chunks_with_evaluation_ids",
        lambda chunks, _corpus: chunks,
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "resolve_chunking_embedding",
        lambda _strategy: ("chunk-embeddings", {"model": "hidden-semantic"}),
    )
    monkeypatch.setattr(rag_eval_runtime, "create_graph_llm", lambda _config: "llm")
    monkeypatch.setattr(
        rag_eval_runtime,
        "create_evaluation_embeddings",
        lambda model, corpus: (
            "langchain-embedding",
            {"model": model, "provider": "fake", "dimensionality": 2},
            {"enabled": False},
        ),
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "create_graph_embedding_model",
        lambda _config, *, langchain_embedding_model: "embedding",
    )
    monkeypatch.setattr(
        rag_eval_runtime, "create_kg_extractors", lambda _config, *, llm: ["simple"]
    )

    def build(**_kwargs):
        if failure == "build":
            raise RuntimeError("build failed")

    monkeypatch.setattr(rag_eval_runtime, "build_property_graph_index", build)
    checks = 0

    async def should_cancel():
        nonlocal checks
        checks += 1
        return failure == "cancel" and checks >= 3

    expected = (
        RuntimeError if failure == "build" else rag_eval_runtime.RagEvaluationCancelled
    )
    with pytest.raises(expected):
        await rag_eval_runtime.GraphRagEvaluationAdapter().prepare(
            specification=_spec("graphrag"),
            corpus=_corpus(),
            run_id=13,
            progress_callback=None,
            should_cancel=should_cancel,
        )

    assert events[-2:] == ["delete", "close"]


@pytest.mark.asyncio
async def test_default_runtime_uses_typed_configuration_and_returns_rich_result(
    monkeypatch,
):
    from app.schemas.llm_models_schemas import (
        LLMModelCatalogItem,
        LLMModelCatalogResponse,
        LLMProviderCatalog,
    )
    from app.schemas.rag_eval_schemas import RagEvalConfigurationCreateRequest
    from app.services import llm_models_service

    models = [
        "gpt-4o-mini",
        "doc-model",
        "rewrite-model",
        "generate-model",
        "hall-model",
        "answer-model",
        "fallback-model",
        "judge-model",
    ]
    monkeypatch.setattr(
        llm_models_service,
        "list_llm_model_catalog",
        lambda: LLMModelCatalogResponse(
            providers=[
                LLMProviderCatalog(
                    provider="openai",
                    models=[LLMModelCatalogItem(name=model) for model in models],
                )
            ]
        ),
    )
    configuration = RagEvalConfigurationCreateRequest.model_validate(
        {
            "name": "typed runtime",
            "chunking": {
                "strategy": "recursive",
                "chunk_size": 100,
                "chunk_overlap": 0,
            },
            "rag": {
                "strategy": "crag",
                "retrieval_embedding_model": "text-embedding-3-small",
                "bm25_weight": 0.0,
                "dense_k": 2,
                "bm25_k": 2,
                "final_top_k": 2,
                "reranker": "none",
                "top_n": 2,
                "max_rewrite_attempts": 3,
                "document_grader": {"provider": "openai", "model": "doc-model"},
                "query_rewriter": {
                    "provider": "openai",
                    "model": "rewrite-model",
                },
                "answer_generator": {
                    "provider": "openai",
                    "model": "generate-model",
                },
                "hallucination_grader": {
                    "provider": "openai",
                    "model": "hall-model",
                },
                "answer_grader": {
                    "provider": "openai",
                    "model": "answer-model",
                },
                "fallback_generator": {
                    "provider": "openai",
                    "model": "fallback-model",
                },
            },
            "metrics": {
                "k": 2,
                "ragas_judge": {"provider": "openai", "model": "judge-model"},
                "judge_embedding_model": "text-embedding-3-small",
            },
        }
    )
    captured = {}
    final_document = Document(
        page_content="final evidence",
        metadata={"evaluation_ids": ["example-1"], "source": "suite.md"},
    )

    class Pipeline:
        resolved_metadata = {"pipeline_version": "pipeline-v1"}

        async def ainvoke(self, _state):
            return {
                "answer": "real answer",
                "documents": [final_document],
                "context": "final evidence",
            }

    def builder(_retriever, pipeline_config):
        captured["pipeline_config"] = pipeline_config
        return Pipeline()

    resources = rag_eval_runtime.EvaluationResources(
        retriever=object(),
        resolved_metadata={"retrieval_embedding": {"model": "selected"}},
        cleanup=lambda: None,
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "adapter_for_strategy",
        lambda strategy: _AdapterForDefault(strategy, resources),
    )
    monkeypatch.setattr(rag_eval_runtime, "build_response_pipeline", builder)

    result = await rag_eval_runtime.create_rag_eval_runtime().run(
        run_id=101,
        configuration=configuration,
        corpus=_corpus(),
    )

    assert captured["pipeline_config"].llm_components == {
        "document_grader": {"provider": "openai", "model": "doc-model"},
        "rewrite": {"provider": "openai", "model": "rewrite-model"},
        "generate": {"provider": "openai", "model": "generate-model"},
        "hallucination_grader": {"provider": "openai", "model": "hall-model"},
        "answer_grader": {"provider": "openai", "model": "answer-model"},
        "fallback": {"provider": "openai", "model": "fallback-model"},
    }
    assert result.results[0].answer == "real answer"
    assert result.results[0].category == "direct_retrieval"
    assert result.results[0].answerable is True
    assert result.results[0].ranked_documents[0].content == "final evidence"
    assert result.resolved_pipeline_snapshot["pipeline_version"] == "pipeline-v1"
    assert result.resolved_pipeline_snapshot["retrieval_embedding"] == {
        "model": "selected"
    }


class _AdapterForDefault:
    def __init__(self, strategy, resources):
        assert strategy == "crag"
        self.resources = resources

    async def prepare(self, **_kwargs):
        return self.resources
