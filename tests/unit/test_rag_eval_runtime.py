from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from app.airag.evaluation.eval_models import EvalCorpus, EvalExample, EvalRunResult
from app.airag.evaluation import rag_eval_runtime


def test_eval_graph_chunks_use_stable_distinct_synthetic_document_ids():
    graph_chunks = rag_eval_runtime._make_eval_graph_chunks(
        [
            Document(page_content="one", metadata={"eval_document_id": "synth_doc_1", "chunk_index": 0}),
            Document(page_content="two", metadata={"eval_document_id": "synth_doc_2", "chunk_index": 0}),
            Document(page_content="three", metadata={"eval_document_id": "synth_doc_1", "chunk_index": 1}),
        ]
    )

    assert graph_chunks[0].raw_document_id == graph_chunks[2].raw_document_id
    assert graph_chunks[0].raw_document_id != graph_chunks[1].raw_document_id


@pytest.mark.asyncio
async def test_crag_runtime_uses_retrieval_embedding_from_run_snapshot(monkeypatch):
    corpus = EvalCorpus(
        documents=(Document(page_content="support", metadata={"eval_document_id": "doc"}),),
        eval_documents=(),
        support_spans=(),
        examples=(EvalExample("example", "Question?", "support", "doc"),),
    )
    captured = {}

    class Store:
        @classmethod
        def from_documents(cls, chunks, embeddings):
            captured["embeddings"] = embeddings
            captured["chunks"] = chunks
            return cls()

        def as_retriever(self, *, search_kwargs):
            captured["search_kwargs"] = search_kwargs
            return object()

    monkeypatch.setattr(rag_eval_runtime, "create_eval_corpus", lambda: corpus)
    monkeypatch.setattr(
        rag_eval_runtime,
        "prepare_evaluation_chunks",
        lambda *_args, **_kwargs: [Document(page_content="support", metadata={"eval_document_id": "doc", "start_index": 0})],
    )
    monkeypatch.setattr(rag_eval_runtime, "tag_chunks_with_evaluation_ids", lambda chunks, _corpus: chunks)
    monkeypatch.setattr(
        rag_eval_runtime,
        "choose_embedding_model",
        lambda model: (captured.setdefault("embedding_model", model), {}),
    )
    monkeypatch.setattr(rag_eval_runtime, "make_invoke_runner", lambda _retriever: object())
    monkeypatch.setattr(
        rag_eval_runtime,
        "run_eval_suite",
        lambda _corpus, _runner, k: EvalRunResult(
            k=k,
            results=(
                rag_eval_runtime.EvalQueryResult(
                    evaluation_id="example",
                    query="Question?",
                    answer=None,
                    reference="support",
                    retrieved_contexts=("support",),
                    retrieved_evaluation_ids=(("example",),),
                    first_relevant_rank=1,
                    hit_at_k=True,
                    reciprocal_rank_at_k=1.0,
                ),
            ),
            hit_rate_at_k=1.0,
            mrr_at_k=1.0,
        ),
    )
    monkeypatch.setitem(__import__("sys").modules, "langchain_community.vectorstores", SimpleNamespace(FAISS=Store))

    result = await rag_eval_runtime.DefaultRagEvalRuntime().run(
        run_id=42,
        rag_snapshot={"strategy": "crag", "config": {"top_k": 2}},
        chunking_snapshot={"strategy": "recursive", "config": {}},
        retrieval_config_snapshot={"embedding_model": "text-embedding-3-large"},
        k=2,
    )

    assert captured["embedding_model"] == "text-embedding-3-large"
    assert captured["search_kwargs"] == {"k": 2}
    assert result.results[0].answer is None


@pytest.mark.asyncio
async def test_crag_runtime_offloads_faiss_build_and_eval_suite(monkeypatch):
    corpus = EvalCorpus(
        documents=(Document(page_content="support", metadata={"eval_document_id": "doc"}),),
        eval_documents=(),
        support_spans=(),
        examples=(EvalExample("example", "Question?", "support", "doc"),),
    )
    calls = []

    class Store:
        @classmethod
        def from_documents(cls, _chunks, _embeddings):
            return cls()

        def as_retriever(self, **_kwargs):
            return object()

    async def recording_to_thread(function, *args, **kwargs):
        calls.append(function)
        return function(*args, **kwargs)

    monkeypatch.setattr(rag_eval_runtime, "create_eval_corpus", lambda: corpus)
    monkeypatch.setattr(
        rag_eval_runtime,
        "prepare_evaluation_chunks",
        lambda *_args, **_kwargs: [Document(page_content="support", metadata={"eval_document_id": "doc"})],
    )
    monkeypatch.setattr(rag_eval_runtime, "tag_chunks_with_evaluation_ids", lambda chunks, _corpus: chunks)
    monkeypatch.setattr(rag_eval_runtime, "choose_embedding_model", lambda _model: (object(), {}))
    monkeypatch.setattr(rag_eval_runtime, "make_invoke_runner", lambda _retriever: object())
    monkeypatch.setattr(
        rag_eval_runtime,
        "run_eval_suite",
        lambda _corpus, _runner, k: EvalRunResult(k=k, results=(), hit_rate_at_k=0.0, mrr_at_k=0.0),
    )
    monkeypatch.setattr(rag_eval_runtime.asyncio, "to_thread", recording_to_thread)
    monkeypatch.setitem(__import__("sys").modules, "langchain_community.vectorstores", SimpleNamespace(FAISS=Store))

    await rag_eval_runtime.DefaultRagEvalRuntime().run(
        run_id=42,
        rag_snapshot={"strategy": "crag", "config": {}},
        chunking_snapshot={"strategy": "recursive", "config": {}},
        retrieval_config_snapshot={"embedding_model": "text-embedding-3-small"},
        k=2,
    )

    assert calls == [rag_eval_runtime.DefaultRagEvalRuntime._run_crag]


@pytest.mark.asyncio
async def test_runtime_reports_chunking_and_retrieving_stages_for_crag(monkeypatch):
    corpus = EvalCorpus(
        documents=(Document(page_content="support", metadata={"eval_document_id": "doc"}),),
        eval_documents=(),
        support_spans=(),
        examples=(EvalExample("example", "Question?", "support", "doc"),),
    )
    stages = []

    class Store:
        @classmethod
        def from_documents(cls, _chunks, _embeddings):
            return cls()

        def as_retriever(self, **_kwargs):
            return object()

    async def record_stage(stage):
        stages.append(stage)

    monkeypatch.setattr(rag_eval_runtime, "create_eval_corpus", lambda: corpus)
    monkeypatch.setattr(
        rag_eval_runtime,
        "prepare_evaluation_chunks",
        lambda *_args, **_kwargs: [Document(page_content="support", metadata={"eval_document_id": "doc"})],
    )
    monkeypatch.setattr(rag_eval_runtime, "tag_chunks_with_evaluation_ids", lambda chunks, _corpus: chunks)
    monkeypatch.setattr(rag_eval_runtime, "choose_embedding_model", lambda _model: (object(), {}))
    monkeypatch.setattr(rag_eval_runtime, "make_invoke_runner", lambda _retriever: object())
    monkeypatch.setattr(
        rag_eval_runtime,
        "run_eval_suite",
        lambda _corpus, _runner, k: EvalRunResult(k=k, results=(), hit_rate_at_k=0.0, mrr_at_k=0.0),
    )
    monkeypatch.setitem(__import__("sys").modules, "langchain_community.vectorstores", SimpleNamespace(FAISS=Store))

    await rag_eval_runtime.DefaultRagEvalRuntime().run(
        run_id=42,
        rag_snapshot={"strategy": "crag", "config": {}},
        chunking_snapshot={"strategy": "recursive", "config": {}},
        retrieval_config_snapshot={"embedding_model": "text-embedding-3-small"},
        k=2,
        stage_callback=record_stage,
    )

    assert stages == ["chunking", "retrieving"]


@pytest.mark.asyncio
async def test_graphrag_runtime_builds_a_scoped_simple_graph_and_deletes_it(monkeypatch):
    corpus = EvalCorpus(
        documents=(Document(page_content="support", metadata={"eval_document_id": "doc"}),),
        eval_documents=(),
        support_spans=(),
        examples=(EvalExample("example", "Question?", "support", "doc"),),
    )
    captured = {"events": []}
    threaded_calls = []

    class Store:
        def __init__(self, **kwargs):
            captured["store_config"] = kwargs

        def delete_generation(self):
            captured["events"].append("delete")
            captured["delete_calls"] = captured.get("delete_calls", 0) + 1

        def close(self):
            captured["closed"] = True

    class Retriever:
        def __init__(self, **kwargs):
            captured["retriever_config"] = kwargs

        def invoke(self, _query):
            graph_chunk = self._chunks_by_id()[1]
            return [Document(page_content=graph_chunk.content, metadata=dict(graph_chunk.chunk_metadata))]

        def _chunks_by_id(self):
            return captured["retriever_config"]["chunks_by_id"]

    monkeypatch.setattr(rag_eval_runtime, "create_eval_corpus", lambda: corpus)
    monkeypatch.setattr(
        rag_eval_runtime,
        "prepare_evaluation_chunks",
        lambda *_args, **_kwargs: [Document(page_content="support", metadata={"eval_document_id": "doc", "start_index": 0, "chunk_index": 0})],
    )
    monkeypatch.setattr(
        rag_eval_runtime,
        "tag_chunks_with_evaluation_ids",
        lambda chunks, _corpus: [Document(page_content=chunks[0].page_content, metadata={**chunks[0].metadata, "evaluation_ids": ["example"]})],
    )
    monkeypatch.setattr(rag_eval_runtime, "ScopedSchemaNeo4jPropertyGraphStore", Store, raising=False)
    monkeypatch.setattr(rag_eval_runtime, "ScopedGraphRetriever", Retriever, raising=False)
    monkeypatch.setattr(rag_eval_runtime, "create_graph_llm", lambda config: captured.setdefault("llm_config", config), raising=False)
    monkeypatch.setattr(rag_eval_runtime, "create_graph_embedding_model", lambda config: captured.setdefault("embedding_config", config), raising=False)
    monkeypatch.setattr(rag_eval_runtime, "create_kg_extractors", lambda config, *, llm: captured.setdefault("extractor_config", config) and [], raising=False)
    def build(**kwargs):
        captured["events"].append("build")
        captured["build"] = kwargs

    async def recording_to_thread(function, *args, **kwargs):
        threaded_calls.append(function)
        return function(*args, **kwargs)

    monkeypatch.setattr(rag_eval_runtime, "build_property_graph_index", build, raising=False)
    monkeypatch.setattr(rag_eval_runtime.asyncio, "to_thread", recording_to_thread)

    result = await rag_eval_runtime.DefaultRagEvalRuntime().run(
        run_id=42,
        rag_snapshot={"strategy": "graphrag", "config": {"retrieval_mode": "semantic", "evidence_limit": 3, "traversal_depth": 2, "rrf_k": 60}},
        chunking_snapshot={"strategy": "recursive", "config": {}},
        retrieval_config_snapshot={
            "embedding_model": "text-embedding-3-small",
            "graph_build": {"llm_provider": "openai", "llm_model": "gpt-4o-mini", "max_paths_per_chunk": 10},
        },
        k=3,
    )

    assert result.hit_rate_at_k == 1.0
    assert captured["store_config"]["graph_id"] == -42
    assert captured["store_config"]["generation"] == "rag-eval"
    assert captured["extractor_config"]["extractors"] == ["simple"]
    assert captured["delete_calls"] == 2
    assert captured["closed"] is True
    assert captured["events"] == ["delete", "build", "delete"]
    assert captured["build"]["nodes"][0].metadata["evaluation_ids"] == ["example"]
    assert result.results[0].retrieved_evaluation_ids == (("example",),)
    assert rag_eval_runtime.run_eval_suite in threaded_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_stage", ["build", "retrieve"])
async def test_graphrag_runtime_deletes_scope_when_build_or_retrieval_fails(monkeypatch, failure_stage):
    corpus = EvalCorpus(
        documents=(Document(page_content="support", metadata={"eval_document_id": "doc"}),),
        eval_documents=(),
        support_spans=(),
        examples=(EvalExample("example", "Question?", "support", "doc"),),
    )
    events = []

    class Store:
        def __init__(self, **_kwargs):
            pass

        def delete_generation(self):
            events.append("delete")

        def close(self):
            events.append("close")

    class Retriever:
        def __init__(self, **_kwargs):
            pass

        def invoke(self, _query):
            raise RuntimeError("retrieval failed")

    def build(**_kwargs):
        events.append("build")
        if failure_stage == "build":
            raise RuntimeError("build failed")

    monkeypatch.setattr(rag_eval_runtime, "create_eval_corpus", lambda: corpus)
    monkeypatch.setattr(
        rag_eval_runtime,
        "prepare_evaluation_chunks",
        lambda *_args, **_kwargs: [Document(page_content="support", metadata={"eval_document_id": "doc"})],
    )
    monkeypatch.setattr(rag_eval_runtime, "tag_chunks_with_evaluation_ids", lambda chunks, _corpus: chunks)
    monkeypatch.setattr(rag_eval_runtime, "ScopedSchemaNeo4jPropertyGraphStore", Store)
    monkeypatch.setattr(rag_eval_runtime, "ScopedGraphRetriever", Retriever)
    monkeypatch.setattr(rag_eval_runtime, "create_graph_llm", lambda _config: object())
    monkeypatch.setattr(rag_eval_runtime, "create_graph_embedding_model", lambda _config: object())
    monkeypatch.setattr(rag_eval_runtime, "create_kg_extractors", lambda _config, *, llm: [])
    monkeypatch.setattr(rag_eval_runtime, "build_property_graph_index", build)

    expected_message = "build failed" if failure_stage == "build" else "retrieval failed"
    with pytest.raises(RuntimeError, match=expected_message):
        await rag_eval_runtime.DefaultRagEvalRuntime().run(
            run_id=42,
            rag_snapshot={"strategy": "graphrag", "config": {}},
            chunking_snapshot={"strategy": "recursive", "config": {}},
            retrieval_config_snapshot={
                "embedding_model": "text-embedding-3-small",
                "graph_build": {"llm_provider": "openai", "llm_model": "gpt-4o-mini"},
            },
            k=2,
        )

    assert events[0] == "delete"
    assert events[-2:] == ["delete", "close"]
