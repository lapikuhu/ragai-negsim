from __future__ import annotations

from dataclasses import dataclass, replace
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from app.airag.evaluation.eval_models import EvalCorpus, EvalExample
from app.airag.evaluation.rag_eval_engine import (
    EvaluationProgress,
    EvaluationResources,
    EvaluationSpecification,
    FullPipelineEvaluator,
    RagEvaluationCancelled,
)


def _corpus(*examples: EvalExample) -> EvalCorpus:
    return EvalCorpus(
        documents=(
            Document(
                page_content="suite source",
                metadata={"eval_document_id": "synth_doc_1"},
            ),
        ),
        eval_documents=(),
        support_spans=(),
        examples=examples,
        suite_version="suite-v2",
        suite_content_hash="suite-hash",
    )


def _specification() -> EvaluationSpecification:
    return EvaluationSpecification(
        strategy="crag",
        chunking={"strategy": "recursive", "chunk_size": 100, "chunk_overlap": 0},
        response_pipeline={
            "reranker": "none",
            "top_n": 2,
            "max_rewrite_attempts": 1,
            "llm_components": {
                name: {"provider": "fake", "model": name}
                for name in (
                    "document_grader",
                    "rewrite",
                    "generate",
                    "hallucination_grader",
                    "answer_grader",
                    "fallback",
                )
            },
        },
        retrieval={"retrieval_embedding_model": "embedding-model", "top_k": 2},
        k=2,
    )


@dataclass
class _Pipeline:
    states: list[dict]
    resolved_metadata: dict

    async def ainvoke(self, state):
        assert state == {"question": self.states[0]["question"]}
        return self.states.pop(0)


class _Adapter:
    def __init__(self, resources):
        self.resources = resources

    async def prepare(self, **_kwargs):
        return self.resources


@pytest.mark.asyncio
async def test_evaluator_invokes_complete_graph_and_keeps_only_final_documents():
    stale = Document(
        page_content="stale retrieval",
        metadata={"evaluation_ids": ["other"], "secret": "drop"},
    )
    final = Document(
        page_content="final evidence",
        metadata={
            "evaluation_ids": ["example-1"],
            "source": "suite.md",
            "score": 0.9,
            "secret": "drop",
        },
    )
    pipeline = _Pipeline(
        states=[
            {
                "question": "Question?",
                "answer": "Graph answer",
                "documents": [final],
                "context": "final evidence",
            }
        ],
        resolved_metadata={"pipeline_version": "pipeline-v1"},
    )
    cleaned = []
    resources = EvaluationResources(
        retriever=object(),
        resolved_metadata={"retrieval_embedding": {"model": "embedding-model"}},
        cleanup=lambda: cleaned.append(True),
    )
    evaluator = FullPipelineEvaluator(
        pipeline_builder=lambda _retriever, _config: pipeline
    )

    result = await evaluator.evaluate(
        specification=_specification(),
        corpus=_corpus(
            EvalExample(
                evaluation_id="example-1",
                category="direct_retrieval",
                answerable=True,
                query="Question?",
                reference_answer="Reference",
            )
        ),
        adapter=_Adapter(resources),
        run_id=7,
    )

    assert stale.page_content not in result.results[0].contexts
    assert result.results[0].answer == "Graph answer"
    assert result.results[0].contexts == ("final evidence",)
    assert result.results[0].ranked_documents[0].rank == 1
    assert result.results[0].ranked_documents[0].metadata == {
        "source": "suite.md",
        "score": 0.9,
    }
    assert result.results[0].ranked_documents[0].evaluation_ids == ("example-1",)
    assert result.resolved_pipeline_snapshot["suite_version"] == "suite-v2"
    assert result.resolved_pipeline_snapshot["suite_content_hash"] == "suite-hash"
    assert cleaned == [True]


@pytest.mark.asyncio
async def test_fallback_empty_context_cannot_expose_stale_retrieval():
    pipeline = _Pipeline(
        states=[
            {
                "question": "Unknown?",
                "answer": "Fallback answer",
                "documents": [
                    Document(
                        page_content="stale retrieval",
                        metadata={"evaluation_ids": ["example-1"]},
                    )
                ],
                "context": "",
            }
        ],
        resolved_metadata={"pipeline_version": "pipeline-v1"},
    )
    resources = EvaluationResources(
        retriever=object(),
        resolved_metadata={},
        cleanup=lambda: None,
    )

    result = await FullPipelineEvaluator(
        pipeline_builder=lambda _retriever, _config: pipeline
    ).evaluate(
        specification=_specification(),
        corpus=_corpus(
            EvalExample(
                evaluation_id="example-1",
                category="unanswerable",
                answerable=False,
                query="Unknown?",
                reference_answer="No answer",
            )
        ),
        adapter=_Adapter(resources),
        run_id=8,
    )

    assert result.results[0].contexts == ()
    assert result.results[0].ranked_documents == ()


@pytest.mark.asyncio
async def test_nonempty_context_uses_authoritative_final_documents_in_order():
    documents = [
        Document(
            page_content="short",
            metadata={"evaluation_ids": ["example-1"], "source": "one"},
        ),
        Document(
            page_content="a longer document containing short",
            metadata={"evaluation_ids": ["example-1"], "source": "two"},
        ),
        Document(
            page_content="short",
            metadata={"evaluation_ids": ["example-1"], "source": "three"},
        ),
    ]
    pipeline = _Pipeline(
        states=[
            {
                "question": "Question?",
                "answer": "Answer",
                "documents": documents,
                "context": "short",
            }
        ],
        resolved_metadata={"pipeline_version": "pipeline-v1"},
    )
    resources = EvaluationResources(
        retriever=object(),
        resolved_metadata={},
        cleanup=lambda: None,
    )

    result = await FullPipelineEvaluator(
        pipeline_builder=lambda _retriever, _config: pipeline
    ).evaluate(
        specification=_specification(),
        corpus=_corpus(EvalExample("example-1", "Question?", "Reference")),
        adapter=_Adapter(resources),
        run_id=81,
    )

    assert result.results[0].contexts == (
        "short",
        "a longer document containing short",
        "short",
    )
    assert [item.rank for item in result.results[0].ranked_documents] == [1, 2, 3]


@pytest.mark.asyncio
async def test_evaluation_metadata_excludes_temporary_graph_scope_identifiers():
    document = Document(
        page_content="graph evidence",
        metadata={
            "evaluation_ids": ["example-1"],
            "source": "suite.md",
            "score": 0.8,
            "chunk_index": 4,
            "graph_id": -91,
            "graph_generation": "rag-eval",
            "raw_document_id": 8,
            "document_chunk_id": 44,
        },
    )
    pipeline = _Pipeline(
        states=[
            {
                "question": "Question?",
                "answer": "Answer",
                "documents": [document],
                "context": "graph evidence",
            }
        ],
        resolved_metadata={"pipeline_version": "pipeline-v1"},
    )
    resources = EvaluationResources(
        retriever=object(),
        resolved_metadata={"extractor": {"implementation": "simple"}},
        cleanup=lambda: None,
    )

    result = await FullPipelineEvaluator(
        pipeline_builder=lambda _retriever, _config: pipeline
    ).evaluate(
        specification=replace(_specification(), strategy="graphrag"),
        corpus=_corpus(EvalExample("example-1", "Question?", "Reference")),
        adapter=_Adapter(resources),
        run_id=91,
    )

    assert result.results[0].ranked_documents[0].metadata == {
        "source": "suite.md",
        "score": 0.8,
        "chunk_index": 4,
    }


@pytest.mark.asyncio
async def test_cancellation_between_examples_reports_progress_and_cleans_up():
    examples = (
        EvalExample("example-1", "First?", "First reference"),
        EvalExample("example-2", "Second?", "Second reference"),
    )
    pipeline = _Pipeline(
        states=[
            {
                "question": "First?",
                "answer": "First answer",
                "documents": [],
                "context": "",
            }
        ],
        resolved_metadata={"pipeline_version": "pipeline-v1"},
    )
    cleaned = []
    resources = EvaluationResources(
        retriever=object(),
        resolved_metadata={},
        cleanup=lambda: cleaned.append(True),
    )
    progress: list[EvaluationProgress] = []
    checks = 0

    async def should_cancel():
        nonlocal checks
        checks += 1
        return checks >= 5

    with pytest.raises(RagEvaluationCancelled):
        await FullPipelineEvaluator(
            pipeline_builder=lambda _retriever, _config: pipeline
        ).evaluate(
            specification=_specification(),
            corpus=_corpus(*examples),
            adapter=_Adapter(resources),
            run_id=9,
            progress_callback=progress.append,
            should_cancel=should_cancel,
        )

    assert any(
        item.stage == "evaluating"
        and item.completed_examples == 1
        and item.total_examples == 2
        for item in progress
    )
    assert progress[-1].stage == "cleaning_up"
    assert [
        item.progress for item in progress if item.stage == "cleaning_up"
    ] == [0.0, 1.0]
    assert cleaned == [True]


@pytest.mark.asyncio
async def test_cleanup_runs_when_cleaning_progress_callback_raises():
    pipeline = _Pipeline(
        states=[
            {
                "question": "Question?",
                "answer": "Answer",
                "documents": [],
                "context": "",
            }
        ],
        resolved_metadata={"pipeline_version": "pipeline-v1"},
    )
    cleaned = []
    resources = EvaluationResources(
        retriever=object(),
        resolved_metadata={},
        cleanup=lambda: cleaned.append(True),
    )

    def progress(update):
        if update.stage == "cleaning_up":
            assert update.progress == 0.0
            raise RuntimeError("progress persistence failed")

    with pytest.raises(RuntimeError, match="progress persistence failed"):
        await FullPipelineEvaluator(
            pipeline_builder=lambda _retriever, _config: pipeline
        ).evaluate(
            specification=_specification(),
            corpus=_corpus(EvalExample("example-1", "Question?", "Reference")),
            adapter=_Adapter(resources),
            run_id=92,
            progress_callback=progress,
        )

    assert cleaned == [True]


def test_core_evaluator_has_no_web_database_or_service_imports():
    from pathlib import Path

    source = Path("app/airag/evaluation/rag_eval_engine.py").read_text()
    forbidden = ("fastapi", "sqlalchemy", "app.services", "app.repositories", "app.models")

    assert not any(name in source for name in forbidden)


@pytest.mark.asyncio
async def test_crag_runtime_exercises_rewrite_generation_quality_and_fallback(
    monkeypatch,
):
    from app.airag import pipeline_factory
    from app.airag.chains.crag import crag as crag_module

    calls = []
    document = Document(
        page_content="final evidence",
        metadata={"evaluation_ids": ["example-1"]},
    )

    class Retriever:
        def invoke(self, query):
            calls.append(("retrieve", query))
            return [document]

    class Runnable:
        def __init__(self, name, function):
            self.name = name
            self.function = function

        def invoke(self, payload, config=None):
            del config
            calls.append((self.name, payload))
            return self.function(payload)

    components = {
        "document_grader": Runnable(
            "grade",
            lambda payload: SimpleNamespace(
                relevance=(
                    "not_relevant"
                    if payload["question"] == "Question?"
                    else "relevant"
                ),
                reasoning="test",
            ),
        ),
        "rewrite": Runnable("rewrite", lambda _payload: "rewritten question"),
        "generate": Runnable("generate", lambda _payload: "draft answer"),
        "hallucination_grader": Runnable(
            "hallucination",
            lambda _payload: SimpleNamespace(grounded="no", reasoning="test"),
        ),
        "answer_grader": Runnable(
            "answer_grade",
            lambda _payload: SimpleNamespace(addresses="no"),
        ),
        "fallback": Runnable("fallback", lambda _payload: "fallback answer"),
    }
    monkeypatch.setattr(
        pipeline_factory,
        "make_crag_component_chains",
        lambda _selections: components,
    )

    def rerank(question, documents, top_n):
        calls.append(("rerank", question, top_n))
        return list(documents[:top_n])

    monkeypatch.setattr(crag_module, "choose_reranker", lambda _name: rerank)
    resources = EvaluationResources(
        retriever=Retriever(),
        resolved_metadata={},
        cleanup=lambda: None,
    )

    result = await FullPipelineEvaluator(
        pipeline_builder=pipeline_factory.build_response_pipeline
    ).evaluate(
        specification=_specification(),
        corpus=_corpus(
            EvalExample(
                evaluation_id="example-1",
                query="Question?",
                reference_answer="Reference",
            )
        ),
        adapter=_Adapter(resources),
        run_id=10,
    )

    assert result.results[0].answer == "fallback answer"
    assert result.results[0].ranked_documents == ()
    assert [call[0] for call in calls] == [
        "retrieve",
        "rerank",
        "grade",
        "rewrite",
        "retrieve",
        "rerank",
        "grade",
        "generate",
        "hallucination",
        "answer_grade",
        "fallback",
    ]
