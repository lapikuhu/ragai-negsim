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


def _spec(strategy: str) -> EvaluationSpecification:
    retrieval = (
        {
            "retrieval_embedding_model": "retrieval-embedding",
            "top_k": 4,
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
                "top_k": 4,
                "reranker": "none",
                "top_n": 4,
                "rewrite_limit": 3,
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


@pytest.mark.asyncio
async def test_crag_adapter_builds_isolated_faiss_with_selected_models_and_top_k(
    monkeypatch,
):
    captured = {}
    tagged = Document(
        page_content="support",
        metadata={
            "eval_document_id": "synth_doc_1",
            "start_index": 0,
            "evaluation_ids": ["example-1"],
        },
    )

    class Store:
        @classmethod
        def from_documents(cls, chunks, embeddings):
            captured["chunks"] = chunks
            captured["embeddings"] = embeddings
            return cls()

        def as_retriever(self, *, search_kwargs):
            captured["search_kwargs"] = search_kwargs
            return "isolated-retriever"

    def prepare_chunks(_documents, _config, **kwargs):
        captured["chunk_kwargs"] = kwargs
        return [tagged]

    monkeypatch.setattr(
        rag_eval_runtime,
        "prepare_evaluation_chunks",
        prepare_chunks,
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "tag_chunks_with_evaluation_ids",
        lambda _chunks, _corpus: [tagged],
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "resolve_chunking_embedding",
        lambda strategy: ("chunk-embeddings", {"model": f"hidden-{strategy}"}),
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "choose_embedding_model",
        lambda model: ("retrieval-embeddings", {"model": model, "provider": "fake"}),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "langchain_community.vectorstores",
        SimpleNamespace(FAISS=Store),
    )

    progress = []
    resources = await rag_eval_runtime.CragEvaluationAdapter().prepare(
        specification=_spec("crag"),
        corpus=_corpus(),
        run_id=11,
        progress_callback=progress.append,
        should_cancel=None,
    )

    assert resources.retriever == "isolated-retriever"
    assert captured["chunk_kwargs"]["embeddings"] == "chunk-embeddings"
    assert captured["embeddings"] == "retrieval-embeddings"
    assert captured["search_kwargs"] == {"k": 4}
    assert resources.resolved_metadata["retrieval_embedding"]["model"] == (
        "retrieval-embedding"
    )
    assert resources.resolved_metadata["chunking_embedding"] == {
        "model": "hidden-semantic"
    }
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
        "create_graph_embedding_model",
        lambda config: captured.setdefault("embedding_config", config) or "embedding",
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "create_kg_extractors",
        lambda config, *, llm: captured.setdefault("extractor_config", config) and [
            "simple"
        ],
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
        rag_eval_runtime, "create_graph_embedding_model", lambda _config: "embedding"
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

    expected = RuntimeError if failure == "build" else rag_eval_runtime.RagEvaluationCancelled
    with pytest.raises(expected):
        await rag_eval_runtime.GraphRagEvaluationAdapter().prepare(
            specification=_spec("graphrag"),
            corpus=_corpus(),
            run_id=13,
            progress_callback=None,
            should_cancel=should_cancel,
        )

    assert events[-2:] == ["delete", "close"]
