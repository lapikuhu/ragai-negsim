from __future__ import annotations

import json

import pytest
from langchain_core.documents import Document

from app.airag.evaluation.eval_models import (
    EvalExecutionResult,
    EvalQueryResult,
)
from app.airag.evaluation.rag_eval_helpers import (
    calculate_hit_rate_at_k,
    calculate_mrr_at_k,
    create_eval_corpus,
    make_invoke_runner,
    run_eval_suite,
    tag_chunks_with_evaluation_ids,
)


def _write_pair(
    tmp_path,
    number: int,
    document_text: str,
    supports: list[dict],
    headings: list[dict] | None = None,
) -> None:
    docs_dir = tmp_path / "synth_docs"
    supports_dir = tmp_path / "supports"
    docs_dir.mkdir(exist_ok=True)
    supports_dir.mkdir(exist_ok=True)
    (docs_dir / f"synth_doc_{number}.md").write_text(document_text, encoding="utf-8")
    (supports_dir / f"support_{number}.md").write_text(
        json.dumps(supports), encoding="utf-8"
    )
    if headings is not None:
        (tmp_path / "support_spans.json").write_text(json.dumps(headings), encoding="utf-8")


def test_create_eval_corpus_pairs_documents_and_assigns_row_ids(tmp_path):
    _write_pair(
        tmp_path,
        1,
        "Intro.\n## Topic\nSource passage.\n## Next\nEnding.",
        [
            {"id": "topic", "query": "First?", "support": "Reference one."},
            {"id": "topic", "query": "Second?", "support": "Reference two."},
        ],
        headings=[
            {"document_number": 1, "row_ordinal": 1, "section_heading": "## Topic"},
            {"document_number": 1, "row_ordinal": 2, "section_heading": "## Topic"},
        ],
    )

    corpus = create_eval_corpus(tmp_path)

    assert len(corpus.documents) == 1
    assert corpus.documents[0].metadata["eval_document_id"] == "synth_doc_1"
    assert [example.evaluation_id for example in corpus.examples] == [
        "synth_doc_1:topic:1",
        "synth_doc_1:topic:2",
    ]
    assert [(span.start, span.end) for span in corpus.support_spans] == [(7, 32), (7, 32)]


def test_create_eval_corpus_rejects_missing_support_span_locator(tmp_path):
    _write_pair(
        tmp_path,
        1,
        "## Topic\nOnly source text.",
        [{"id": "topic", "query": "Question?", "support": "Missing support."}],
    )

    with pytest.raises(ValueError, match="Missing support span locator"):
        create_eval_corpus(tmp_path)


def test_create_eval_corpus_rejects_ambiguous_section_heading(tmp_path):
    _write_pair(
        tmp_path,
        1,
        "## Topic\nOne.\n## Topic\nTwo.",
        [{"id": "topic", "query": "Question?", "support": "Repeated."}],
        headings=[{"document_number": 1, "row_ordinal": 1, "section_heading": "## Topic"}],
    )

    with pytest.raises(ValueError, match="multiple times"):
        create_eval_corpus(tmp_path)


def test_tag_chunks_with_evaluation_ids_preserves_metadata_and_tags_overlap(tmp_path):
    _write_pair(
        tmp_path,
        1,
        "Intro.\n## Topic\nSource passage.\n## Next\nEnding.",
        [{"id": "topic", "query": "Question?", "support": "Reference."}],
        headings=[{"document_number": 1, "row_ordinal": 1, "section_heading": "## Topic"}],
    )
    corpus = create_eval_corpus(tmp_path)
    chunks = [
        Document(
            page_content="Source passage.",
            metadata={"eval_document_id": "synth_doc_1", "start_index": 15, "keep": True},
        ),
        Document(
            page_content="Ending.",
            metadata={"eval_document_id": "synth_doc_1", "start_index": 39},
        ),
    ]

    tagged = tag_chunks_with_evaluation_ids(chunks, corpus)

    assert tagged[0].metadata["evaluation_ids"] == ["synth_doc_1:topic:1"]
    assert tagged[0].metadata["keep"] is True
    assert "evaluation_ids" not in tagged[1].metadata


def test_run_eval_suite_calculates_hit_rate_and_mrr_at_k(tmp_path):
    _write_pair(
        tmp_path,
        1,
        "## One\nSource one.\n## Two\nSource two.",
        [
            {"id": "one", "query": "One?", "support": "One."},
            {"id": "two", "query": "Two?", "support": "Two."},
        ],
        headings=[
            {"document_number": 1, "row_ordinal": 1, "section_heading": "## One"},
            {"document_number": 1, "row_ordinal": 2, "section_heading": "## Two"},
        ],
    )
    corpus = create_eval_corpus(tmp_path)

    def runner(query: str) -> EvalExecutionResult:
        if query == "One?":
            return EvalExecutionResult(
                answer="one answer",
                documents=[
                    Document(page_content="irrelevant", metadata={}),
                    Document(page_content="one", metadata={"evaluation_ids": ["synth_doc_1:one:1"]}),
                ],
            )
        return EvalExecutionResult(answer="two answer", documents=[])

    result = run_eval_suite(corpus, runner, k=2)

    assert result.hit_rate_at_k == 0.5
    assert result.mrr_at_k == 0.25
    assert result.results[0].answer == "one answer"
    assert result.results[0].reference == "One."
    assert result.results[0].retrieved_contexts == ("irrelevant", "one")
    assert result.results[0].first_relevant_rank == 2
    assert result.results[1].first_relevant_rank is None


def test_run_eval_suite_applies_rank_cutoff_and_validates_k(tmp_path):
    _write_pair(
        tmp_path,
        1,
        "## Topic\nSource passage.",
        [{"id": "topic", "query": "Question?", "support": "Expected support."}],
        headings=[{"document_number": 1, "row_ordinal": 1, "section_heading": "## Topic"}],
    )
    corpus = create_eval_corpus(tmp_path)

    runner = lambda _query: EvalExecutionResult(
        answer=None,
        documents=[
            Document(page_content="x", metadata={}),
            Document(page_content="x", metadata={"evaluation_ids": ["synth_doc_1:topic:1"]}),
        ],
    )

    result = run_eval_suite(corpus, runner, k=1)

    assert result.hit_rate_at_k == 0.0
    assert result.mrr_at_k == 0.0
    with pytest.raises(ValueError, match="k must be at least 1"):
        run_eval_suite(corpus, runner, k=0)


def test_make_invoke_runner_normalizes_langchain_retriever_documents():
    class Retriever:
        def invoke(self, query: str):
            assert query == "Question?"
            return [Document(page_content="context", metadata={})]

    result = make_invoke_runner(Retriever())("Question?")

    assert result.answer is None
    assert result.documents[0].page_content == "context"


def test_calculate_hit_rate_at_k_averages_query_hits():
    results = [
        EvalQueryResult("one", "One?", None, "Reference", (), (), 1, True, 1.0),
        EvalQueryResult("two", "Two?", None, "Reference", (), (), None, False, 0.0),
    ]

    assert calculate_hit_rate_at_k(results) == 0.5


def test_calculate_mrr_at_k_averages_first_relevant_ranks():
    results = [
        EvalQueryResult("one", "One?", None, "Reference", (), (), 1, True, 1.0),
        EvalQueryResult("two", "Two?", None, "Reference", (), (), 2, True, 0.5),
        EvalQueryResult("three", "Three?", None, "Reference", (), (), None, False, 0.0),
    ]

    assert calculate_mrr_at_k(results) == pytest.approx(0.5)
