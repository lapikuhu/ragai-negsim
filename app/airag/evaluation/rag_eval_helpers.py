"""Validated, in-memory helpers for the versioned synthetic evaluation suite."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from langchain_core.documents import Document

from app.airag.evaluation.eval_models import (
    EvalCorpus,
    EvalDocument,
    EvalExample,
    EvalExecutionResult,
    EvalQueryResult,
    EvalRunner,
    EvalRunResult,
    EvalSourceDocument,
    EvalSpanLocator,
    EvalSupportRow,
    EvalSupportSpan,
)


_SYNTHETIC_DOCUMENT_NAME = re.compile(r"^synth_doc_(?P<number>[1-9]\d*)\.md$")
_SUPPORT_NAME = re.compile(r"^support_(?P<number>[1-9]\d*)\.md$")
_CATEGORIES = {
    "direct_retrieval",
    "paraphrased_retrieval",
    "answerable_hard_negative",
    "unanswerable",
    "relational_multi_hop",
}
_REAL_CATEGORY_COUNTS = {
    "direct_retrieval": 20,
    "paraphrased_retrieval": 20,
    "answerable_hard_negative": 10,
    "unanswerable": 10,
    "relational_multi_hop": 20,
}


def _suite_root(root: str | Path | None) -> Path:
    return Path(root) if root is not None else Path(__file__).resolve().parent


def _discover_numbered_files(
    directory: Path, pattern: re.Pattern[str], kind: str
) -> dict[int, Path]:
    if not directory.is_dir():
        raise ValueError(f"Evaluation {kind} directory does not exist: {directory}")
    files: dict[int, Path] = {}
    for path in directory.iterdir():
        if not path.is_file() or path.suffix != ".md":
            continue
        match = pattern.fullmatch(path.name)
        if match is None:
            raise ValueError(f"Invalid evaluation {kind} filename: {path.name}")
        number = int(match.group("number"))
        if number in files:
            raise ValueError(f"Duplicate evaluation {kind} number: {number}")
        files[number] = path
    if files and sorted(files) != list(range(1, max(files) + 1)):
        raise ValueError(f"Evaluation {kind} numbering must be sequential from 1")
    return files


def load_eval_documents(root: str | Path | None = None) -> dict[int, EvalSourceDocument]:
    paths = _discover_numbered_files(
        _suite_root(root) / "synth_docs", _SYNTHETIC_DOCUMENT_NAME, "document"
    )
    return {
        number: EvalSourceDocument(
            document_id=f"synth_doc_{number}",
            number=number,
            path=path,
            content=path.read_text(encoding="utf-8"),
        )
        for number, path in paths.items()
    }


def load_eval_supports(
    root: str | Path | None = None,
) -> dict[int, tuple[EvalSupportRow, ...]]:
    paths = _discover_numbered_files(
        _suite_root(root) / "supports", _SUPPORT_NAME, "support"
    )
    loaded: dict[int, tuple[EvalSupportRow, ...]] = {}
    for number, path in paths.items():
        try:
            raw_rows = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid support JSON in {path.name}: {exc.msg}") from exc
        if not isinstance(raw_rows, list):
            raise ValueError(f"Support file {path.name} must contain a JSON array")
        rows: list[EvalSupportRow] = []
        for ordinal, raw in enumerate(raw_rows, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"Support row {ordinal} in {path.name} must be an object")
            for field in ("id", "category", "query", "reference_answer"):
                value = raw.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"Support row {ordinal} in {path.name} has invalid {field!r}"
                    )
            answerable = raw.get("answerable")
            if not isinstance(answerable, bool):
                raise ValueError(
                    f"Support row {ordinal} in {path.name} has invalid 'answerable'"
                )
            category = raw["category"]
            if category not in _CATEGORIES:
                raise ValueError(f"Support row {ordinal} in {path.name} has invalid category")
            bridge_entity = raw.get("bridge_entity")
            if category == "relational_multi_hop" and (
                not isinstance(bridge_entity, str) or not bridge_entity.strip()
            ):
                raise ValueError(
                    f"Relational support row {ordinal} in {path.name} "
                    "requires a named bridge_entity"
                )
            if bridge_entity is not None and not isinstance(bridge_entity, str):
                raise ValueError(
                    f"Support row {ordinal} in {path.name} has invalid bridge_entity"
                )
            rows.append(
                EvalSupportRow(
                    evaluation_id=raw["id"],
                    category=category,
                    answerable=answerable,
                    query=raw["query"],
                    reference_answer=raw["reference_answer"],
                    ordinal=ordinal,
                    bridge_entity=bridge_entity,
                )
            )
        loaded[number] = tuple(rows)
    return loaded


def load_eval_span_locators(
    root: str | Path | None = None,
) -> tuple[str, tuple[EvalSpanLocator, ...]]:
    path = _suite_root(root) / "support_spans.json"
    if not path.is_file():
        raise ValueError(f"Missing support span locator file: {path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid support span locator JSON: {exc.msg}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Support span locator manifest must be an object")
    version = manifest.get("version")
    raw_locators = manifest.get("locators")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Support span locator manifest requires a version")
    if not isinstance(raw_locators, list):
        raise ValueError("Support span locator manifest requires a locators array")

    locators: list[EvalSpanLocator] = []
    seen: set[tuple[str, int, str]] = set()
    for position, raw in enumerate(raw_locators, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Support span locator {position} must be an object")
        evaluation_id = raw.get("example_id")
        document_number = raw.get("document_number")
        quote = raw.get("quote")
        if not isinstance(evaluation_id, str) or not evaluation_id.strip():
            raise ValueError(f"Support span locator {position} has invalid example_id")
        if (
            isinstance(document_number, bool)
            or not isinstance(document_number, int)
            or document_number < 1
        ):
            raise ValueError(
                f"Support span locator {position} has invalid document_number"
            )
        if not isinstance(quote, str) or not quote.strip():
            raise ValueError(f"Support span locator {position} has invalid quote")
        key = (evaluation_id, document_number, quote)
        if key in seen:
            raise ValueError(
                f"Duplicate support span locator for example {evaluation_id!r}"
            )
        seen.add(key)
        locators.append(EvalSpanLocator(evaluation_id, document_number, quote))
    return version, tuple(locators)


def pair_eval_documents_and_supports(
    documents: dict[int, EvalSourceDocument],
    supports: dict[int, tuple[EvalSupportRow, ...]],
) -> tuple[tuple[EvalSourceDocument, tuple[EvalSupportRow, ...]], ...]:
    document_numbers = set(documents)
    support_numbers = set(supports)
    if document_numbers != support_numbers:
        missing_supports = sorted(document_numbers - support_numbers)
        missing_documents = sorted(support_numbers - document_numbers)
        details = []
        if missing_supports:
            details.append(f"missing support files for {missing_supports}")
        if missing_documents:
            details.append(f"missing source documents for {missing_documents}")
        raise ValueError("Unmatched evaluation files: " + "; ".join(details))
    if not document_numbers:
        raise ValueError("Evaluation suite contains no document/support pairs")
    return tuple((documents[number], supports[number]) for number in sorted(document_numbers))


def _find_unique_quote(document: EvalSourceDocument, locator: EvalSpanLocator) -> tuple[int, int]:
    first = document.content.find(locator.quote)
    if first < 0:
        raise ValueError(
            f"Support quote for {locator.evaluation_id!r} is not found in {document.path.name}"
        )
    if document.content.find(locator.quote, first + 1) >= 0:
        raise ValueError(
            f"Support quote for {locator.evaluation_id!r} occurs multiple times in "
            f"{document.path.name}"
        )
    end = first + len(locator.quote)
    if first < 0 or end > len(document.content):
        raise ValueError(f"Support locator for {locator.evaluation_id!r} is out of bounds")
    return first, end


def _suite_content_hash(
    root: Path,
    document_numbers: Sequence[int],
    support_numbers: Sequence[int],
) -> str:
    relative_paths = ["support_spans.json"]
    relative_paths.extend(
        f"synth_docs/synth_doc_{number}.md" for number in document_numbers
    )
    relative_paths.extend(f"supports/support_{number}.md" for number in support_numbers)
    digest = hashlib.sha256()
    for relative_path in sorted(relative_paths):
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update((root / relative_path).read_bytes())
    return digest.hexdigest()


def create_eval_corpus(
    root: str | Path | None = None,
    *,
    expected_category_counts: Mapping[str, int] | None = None,
) -> EvalCorpus:
    suite_root = _suite_root(root)
    documents = load_eval_documents(suite_root)
    supports = load_eval_supports(suite_root)
    pairs = pair_eval_documents_and_supports(documents, supports)
    version, locators = load_eval_span_locators(suite_root)
    expected = dict(
        _REAL_CATEGORY_COUNTS
        if expected_category_counts is None
        else expected_category_counts
    )

    rows = [row for _, paired_rows in pairs for row in paired_rows]
    ids = [row.evaluation_id for row in rows]
    duplicate_ids = sorted(
        evaluation_id
        for evaluation_id, count in Counter(ids).items()
        if count > 1
    )
    if duplicate_ids:
        raise ValueError(f"Duplicate evaluation example ID: {duplicate_ids[0]}")
    actual_counts = Counter(row.category for row in rows)
    if actual_counts != Counter(expected):
        raise ValueError(
            f"Invalid evaluation category distribution: expected {expected}, "
            f"found {dict(actual_counts)}"
        )

    rows_by_id = {row.evaluation_id: row for row in rows}
    spans_by_example: dict[str, list[EvalSupportSpan]] = {}
    spans_by_document: dict[str, list[EvalSupportSpan]] = {}
    for locator in locators:
        row = rows_by_id.get(locator.evaluation_id)
        if row is None:
            raise ValueError(
                f"Support locator references unknown example {locator.evaluation_id!r}"
            )
        document = documents.get(locator.document_number)
        if document is None:
            raise ValueError(
                f"Support locator for {locator.evaluation_id!r} references unknown document "
                f"{locator.document_number}"
            )
        start, end = _find_unique_quote(document, locator)
        span = EvalSupportSpan(
            evaluation_id=row.evaluation_id,
            support_id=row.evaluation_id,
            document_id=document.document_id,
            query=row.query,
            support=locator.quote,
            start=start,
            end=end,
        )
        spans_by_example.setdefault(row.evaluation_id, []).append(span)
        spans_by_document.setdefault(document.document_id, []).append(span)

    examples: list[EvalExample] = []
    for row in rows:
        spans = tuple(spans_by_example.get(row.evaluation_id, ()))
        if row.category == "unanswerable" and row.answerable:
            raise ValueError(
                f"Unanswerable example {row.evaluation_id!r} must be marked unanswerable"
            )
        if row.category != "unanswerable" and not row.answerable:
            raise ValueError(
                f"Example {row.evaluation_id!r} must use the unanswerable category"
            )
        if row.answerable and not spans:
            raise ValueError(
                f"Answerable example {row.evaluation_id!r} must have at least one support locator"
            )
        if not row.answerable and spans:
            raise ValueError(
                f"Unanswerable example {row.evaluation_id!r} must not have support locators"
            )
        if row.category == "relational_multi_hop":
            bridge = row.bridge_entity or ""
            if bridge in row.query:
                raise ValueError(
                    f"Relational example {row.evaluation_id!r} query must not encode "
                    "its bridge entity"
                )
            if len(spans) < 2 or len({span.document_id for span in spans}) < 2:
                raise ValueError(
                    f"Relational example {row.evaluation_id!r} requires evidence "
                    "from at least two documents"
                )
            if any(bridge not in span.support for span in spans):
                raise ValueError(
                    f"Relational example {row.evaluation_id!r} bridge entity must "
                    "appear in every evidence passage"
                )
        examples.append(
            EvalExample(
                evaluation_id=row.evaluation_id,
                category=row.category,
                answerable=row.answerable,
                query=row.query,
                reference_answer=row.reference_answer,
                support_spans=spans,
                bridge_entity=row.bridge_entity,
            )
        )

    ordered_documents = [documents[number] for number in sorted(documents)]
    eval_documents = tuple(
        EvalDocument(
            document_id=document.document_id,
            path=document.path,
            content=document.content,
            support_spans=tuple(spans_by_document.get(document.document_id, ())),
        )
        for document in ordered_documents
    )
    source_documents = tuple(
        Document(
            page_content=document.content,
            metadata={
                "eval_document_id": document.document_id,
                "source": str(document.path),
            },
        )
        for document in ordered_documents
    )
    support_spans = tuple(
        span for document in eval_documents for span in document.support_spans
    )
    return EvalCorpus(
        documents=source_documents,
        eval_documents=eval_documents,
        support_spans=support_spans,
        examples=tuple(examples),
        suite_version=version,
        suite_content_hash=_suite_content_hash(
            suite_root, sorted(documents), sorted(supports)
        ),
    )


def tag_chunks_with_evaluation_ids(
    chunks: Sequence[Document], corpus: EvalCorpus
) -> list[Document]:
    spans_by_document: dict[str, list[EvalSupportSpan]] = {}
    for span in corpus.support_spans:
        spans_by_document.setdefault(span.document_id, []).append(span)
    tagged: list[Document] = []
    for chunk in chunks:
        metadata = dict(chunk.metadata)
        document_id = metadata.get("eval_document_id")
        start = metadata.get("start_index")
        if not isinstance(document_id, str) or not isinstance(start, int):
            raise ValueError(
                "Chunks must include string eval_document_id and integer start_index metadata"
            )
        end = metadata.get("end_index", start + len(chunk.page_content))
        if not isinstance(end, int) or end < start:
            raise ValueError(
                "Chunk end_index must be an integer greater than or equal to start_index"
            )
        overlapping_ids = [
            span.evaluation_id
            for span in spans_by_document.get(document_id, [])
            if start < span.end and end > span.start
        ]
        if overlapping_ids:
            existing_ids = metadata.get("evaluation_ids", [])
            if not isinstance(existing_ids, list) or not all(
                isinstance(item, str) for item in existing_ids
            ):
                raise ValueError("Chunk evaluation_ids metadata must be a list of strings")
            metadata["evaluation_ids"] = list(
                dict.fromkeys([*existing_ids, *overlapping_ids])
            )
        tagged.append(Document(page_content=chunk.page_content, metadata=metadata))
    return tagged


def _document_evaluation_ids(document: Document) -> tuple[str, ...]:
    evaluation_ids = document.metadata.get("evaluation_ids", [])
    if not isinstance(evaluation_ids, list) or not all(
        isinstance(item, str) for item in evaluation_ids
    ):
        raise ValueError(
            "Retrieved document evaluation_ids metadata must be a list of strings"
        )
    return tuple(evaluation_ids)


def calculate_hit_rate_at_k(results: Sequence[EvalQueryResult]) -> float:
    if not results:
        raise ValueError("Cannot calculate HitRate@k for an empty result set")
    return sum(result.hit_at_k for result in results) / len(results)


def calculate_mrr_at_k(results: Sequence[EvalQueryResult]) -> float:
    if not results:
        raise ValueError("Cannot calculate MRR@k for an empty result set")
    return sum(result.reciprocal_rank_at_k for result in results) / len(results)


def run_eval_suite(corpus: EvalCorpus, runner: EvalRunner, k: int) -> EvalRunResult:
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be at least 1")
    query_results: list[EvalQueryResult] = []
    for example in corpus.examples:
        execution = runner(example.query)
        if not isinstance(execution, EvalExecutionResult):
            raise ValueError("EvalRunner must return EvalExecutionResult")
        retrieved_ids = tuple(
            _document_evaluation_ids(document) for document in execution.documents
        )
        # First-relevant Hit@k/MRR@k intentionally stay unchanged for multi-locator
        # examples. Required-evidence coverage@k and all-evidence-hit@k are future metrics.
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
                evaluation_id=example.evaluation_id,
                query=example.query,
                answer=execution.answer,
                reference=example.reference_answer,
                retrieved_contexts=tuple(
                    document.page_content for document in execution.documents
                ),
                retrieved_evaluation_ids=retrieved_ids,
                first_relevant_rank=first_rank,
                hit_at_k=first_rank is not None,
                reciprocal_rank_at_k=0.0 if first_rank is None else 1.0 / first_rank,
            )
        )
    if not query_results:
        raise ValueError("Evaluation corpus contains no examples")
    return EvalRunResult(
        k=k,
        results=tuple(query_results),
        hit_rate_at_k=calculate_hit_rate_at_k(query_results),
        mrr_at_k=calculate_mrr_at_k(query_results),
    )
