from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from app.airag.evaluation.rag_eval_helpers import create_eval_corpus


DIRECT = "direct_retrieval"
PARAPHRASED = "paraphrased_retrieval"
HARD_NEGATIVE = "answerable_hard_negative"
UNANSWERABLE = "unanswerable"
MULTI_HOP = "relational_multi_hop"
REAL_COUNTS = {
    DIRECT: 20,
    PARAPHRASED: 20,
    HARD_NEGATIVE: 10,
    UNANSWERABLE: 10,
    MULTI_HOP: 20,
}


def _write_suite(
    root: Path,
    *,
    documents: dict[int, str],
    supports: dict[int, list[dict]],
    locators: list[dict],
) -> None:
    (root / "synth_docs").mkdir()
    (root / "supports").mkdir()
    for number, content in documents.items():
        (root / "synth_docs" / f"synth_doc_{number}.md").write_text(
            content, encoding="utf-8"
        )
    for number, rows in supports.items():
        (root / "supports" / f"support_{number}.md").write_text(
            json.dumps(rows, ensure_ascii=False), encoding="utf-8"
        )
    (root / "support_spans.json").write_text(
        json.dumps({"version": "1.0", "locators": locators}, ensure_ascii=False),
        encoding="utf-8",
    )


def _row(
    example_id: str,
    category: str = DIRECT,
    *,
    answerable: bool = True,
) -> dict:
    return {
        "id": example_id,
        "category": category,
        "answerable": answerable,
        "query": f"Question for {example_id}?",
        "reference_answer": (
            f"Answer for {example_id}." if answerable else "Not answerable from the corpus."
        ),
    }


def _locator(example_id: str, number: int, quote: str) -> dict:
    return {"example_id": example_id, "document_number": number, "quote": quote}


def _create_small_suite(tmp_path: Path):
    _write_suite(
        tmp_path,
        documents={
            1: "Alpha evidence gives the first fact.\n\nShared bridge fact.",
            2: "Beta evidence gives the second fact.",
        },
        supports={
            1: [_row("direct-001"), _row("multi-001", MULTI_HOP)],
            2: [_row("unanswerable-001", UNANSWERABLE, answerable=False)],
        },
        locators=[
            _locator("direct-001", 1, "Alpha evidence gives the first fact."),
            _locator("multi-001", 1, "Shared bridge fact."),
            _locator("multi-001", 2, "Beta evidence gives the second fact."),
        ],
    )
    return create_eval_corpus(
        tmp_path,
        expected_category_counts={DIRECT: 1, MULTI_HOP: 1, UNANSWERABLE: 1},
    )


def test_suite_supports_multi_locator_and_cross_document_evidence(tmp_path):
    corpus = _create_small_suite(tmp_path)

    multi = next(example for example in corpus.examples if example.evaluation_id == "multi-001")
    assert multi.category == MULTI_HOP
    assert multi.answerable is True
    assert [span.document_id for span in multi.support_spans] == [
        "synth_doc_1",
        "synth_doc_2",
    ]
    assert [span.support for span in multi.support_spans] == [
        "Shared bridge fact.",
        "Beta evidence gives the second fact.",
    ]


@pytest.mark.parametrize(
    ("documents", "supports", "match"),
    [
        (
            {1: "One.", 3: "Three."},
            {1: [_row("one")], 3: [_row("three")]},
            "sequential",
        ),
        (
            {1: "One.", 2: "Two."},
            {1: [_row("one")]},
            "Unmatched evaluation files",
        ),
    ],
)
def test_suite_rejects_nonsequential_or_unpaired_files(
    tmp_path, documents, supports, match
):
    locators = [
        _locator(row["id"], number, documents[number])
        for number, rows in supports.items()
        for row in rows
    ]
    _write_suite(
        tmp_path, documents=documents, supports=supports, locators=locators
    )

    with pytest.raises(ValueError, match=match):
        create_eval_corpus(tmp_path, expected_category_counts={DIRECT: len(locators)})


def test_suite_rejects_duplicate_stable_example_ids(tmp_path):
    _write_suite(
        tmp_path,
        documents={1: "One.", 2: "Two."},
        supports={1: [_row("duplicate")], 2: [_row("duplicate")]},
        locators=[_locator("duplicate", 1, "One.")],
    )

    with pytest.raises(ValueError, match="Duplicate evaluation example ID"):
        create_eval_corpus(tmp_path, expected_category_counts={DIRECT: 2})


def test_suite_rejects_wrong_category_distribution(tmp_path):
    _write_suite(
        tmp_path,
        documents={1: "One."},
        supports={1: [_row("one")]},
        locators=[_locator("one", 1, "One.")],
    )

    with pytest.raises(ValueError, match="category distribution"):
        create_eval_corpus(tmp_path, expected_category_counts={PARAPHRASED: 1})


@pytest.mark.parametrize(
    ("documents", "locators", "match"),
    [
        (
            {1: "Repeated quote. Repeated quote."},
            [_locator("one", 1, "Repeated quote.")],
            "multiple times",
        ),
        (
            {1: "Only text."},
            [_locator("one", 1, "Missing text.")],
            "not found",
        ),
        (
            {1: "Only text."},
            [
                _locator("one", 1, "Only text."),
                _locator("one", 1, "Only text."),
            ],
            "Duplicate support span locator",
        ),
        (
            {1: "Only text."},
            [_locator("one", 2, "Only text.")],
            "unknown document",
        ),
    ],
)
def test_suite_rejects_nonunique_or_out_of_bounds_locators(
    tmp_path, documents, locators, match
):
    _write_suite(
        tmp_path,
        documents=documents,
        supports={1: [_row("one")]},
        locators=locators,
    )

    with pytest.raises(ValueError, match=match):
        create_eval_corpus(tmp_path, expected_category_counts={DIRECT: 1})


@pytest.mark.parametrize(
    ("row", "locators", "match"),
    [
        (_row("answerable"), [], "must have at least one"),
        (
            _row("not-answerable", UNANSWERABLE, answerable=False),
            [_locator("not-answerable", 1, "Only text.")],
            "must not have support locators",
        ),
        (
            _row("wrong-category", DIRECT, answerable=False),
            [],
            "unanswerable category",
        ),
        (
            _row("wrong-flag", UNANSWERABLE, answerable=True),
            [_locator("wrong-flag", 1, "Only text.")],
            "must be marked unanswerable",
        ),
    ],
)
def test_suite_enforces_answerability_rules(tmp_path, row, locators, match):
    _write_suite(
        tmp_path,
        documents={1: "Only text."},
        supports={1: [row]},
        locators=locators,
    )

    with pytest.raises(ValueError, match=match):
        create_eval_corpus(
            tmp_path, expected_category_counts={row["category"]: 1}
        )


def test_suite_hash_is_deterministic_and_covers_raw_used_files(tmp_path):
    corpus = _create_small_suite(tmp_path)
    relative_paths = [
        "support_spans.json",
        "supports/support_1.md",
        "supports/support_2.md",
        "synth_docs/synth_doc_1.md",
        "synth_docs/synth_doc_2.md",
    ]
    digest = hashlib.sha256()
    for relative_path in sorted(relative_paths):
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update((tmp_path / relative_path).read_bytes())

    assert corpus.suite_version == "1.0"
    assert corpus.suite_content_hash == digest.hexdigest()
    assert create_eval_corpus(
        tmp_path,
        expected_category_counts={DIRECT: 1, MULTI_HOP: 1, UNANSWERABLE: 1},
    ).suite_content_hash == corpus.suite_content_hash

    path = tmp_path / "synth_docs" / "synth_doc_1.md"
    path.write_bytes(path.read_bytes() + b"\n")
    changed = create_eval_corpus(
        tmp_path,
        expected_category_counts={DIRECT: 1, MULTI_HOP: 1, UNANSWERABLE: 1},
    )
    assert changed.suite_content_hash != corpus.suite_content_hash


def test_real_suite_has_exact_reviewed_distribution_and_precise_locators():
    corpus = create_eval_corpus()

    assert len(corpus.examples) == 80
    assert Counter(example.category for example in corpus.examples) == REAL_COUNTS
    assert len({example.evaluation_id for example in corpus.examples}) == 80
    assert all(example.support_spans for example in corpus.examples if example.answerable)
    assert all(not example.support_spans for example in corpus.examples if not example.answerable)
    assert all(
        0 <= span.start < span.end <= len(document.content)
        for document in corpus.eval_documents
        for span in document.support_spans
    )
    assert any(
        len({span.document_id for span in example.support_spans}) > 1
        for example in corpus.examples
        if example.category == MULTI_HOP
    )
