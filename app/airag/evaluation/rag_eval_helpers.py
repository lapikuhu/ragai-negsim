"""In-memory helpers for evaluating retrieval against the synthetic suite."""

from __future__ import annotations
from collections.abc import Sequence
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
    EvalSourceDocument,
    EvalSpanLocator,
    EvalSupportRow,
    EvalSupportSpan,
    EvalRunResult,
)


_SYNTHETIC_DOCUMENT_NAME = re.compile(r"^synth_doc_(?P<number>[1-9]\d*)\.md$")
_SUPPORT_NAME = re.compile(r"^support_(?P<number>[1-9]\d*)\.md$")
_REQUIRED_SUPPORT_FIELDS = ("id", "query", "support")


def _suite_root(root: str | Path | None) -> Path:
    return Path(root) if root is not None else Path(__file__).resolve().parent


def _discover_numbered_files(directory: Path, pattern: re.Pattern[str], kind: str) -> dict[int, Path]:
    """
    Discover numbered files in a directory matching a pattern.
    Args:
        directory: The directory to search for files.
        pattern: A compiled regular expression pattern to match filenames.
        kind: A descriptive name for the type of files being discovered.

    Returns:
        A dictionary mapping file numbers to their corresponding paths.
    Raises:
        ValueError: If the directory does not exist, or if there are duplicate or invalid filenames.
    """
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
    return files


def load_eval_documents(root: str | Path | None = None) -> dict[int, EvalSourceDocument]:
    """
    Load synthetic source documents from ``synth_docs`` without persistence.
    Args:
        root: Optional root directory for the evaluation suite. If None, 
            defaults to the directory of this file.
    Returns:
        A dictionary mapping document numbers to EvalSourceDocument instances.
    """
    suite_root = _suite_root(root)
    paths = _discover_numbered_files(
        suite_root / "synth_docs", _SYNTHETIC_DOCUMENT_NAME, "document"
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


def load_eval_supports(root: str | Path | None = None) -> dict[int, tuple[EvalSupportRow, ...]]:
    """
    Load and validate support JSON arrays from ``supports``.
    Args:
        root: Optional root directory for the evaluation suite. If None, 
            defaults to the directory of this file.
    Returns:
        A dictionary mapping support numbers to tuples of EvalSupportRow 
        instances.
    Raises:
        ValueError: If any support file is invalid or missing required fields.
    """
    suite_root = _suite_root(root)
    paths = _discover_numbered_files(suite_root / "supports", _SUPPORT_NAME, "support")
    loaded: dict[int, tuple[EvalSupportRow, ...]] = {}
    for number, path in paths.items():
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid support JSON in {path.name}: {exc.msg}") from exc
        if not isinstance(rows, list):
            raise ValueError(f"Support file {path.name} must contain a JSON array")

        supports: list[EvalSupportRow] = []
        for ordinal, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise ValueError(f"Support row {ordinal} in {path.name} must be an object")
            for field in _REQUIRED_SUPPORT_FIELDS:
                value = row.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"Support row {ordinal} in {path.name} has invalid {field!r}"
                    )
            supports.append(
                EvalSupportRow(
                    support_id=row["id"],
                    query=row["query"],
                    support=row["support"],
                    ordinal=ordinal,
                )
            )
        loaded[number] = tuple(supports)
    return loaded


def load_eval_span_locators(root: str | Path | None = None) -> dict[tuple[int, int], EvalSpanLocator]:
    """
    Load human-curated source-passage locators from ``support_spans.json``.
    Args:
        root: Optional root directory for the evaluation suite. If None,
            defaults to the directory of this file.
    Returns:
        A dictionary mapping (document_number, row_ordinal) tuples to 
        EvalSpanLocator instances.
    Raises:
        ValueError: If the support span locator file is missing or contains invalid data.
    """
    path = _suite_root(root) / "support_spans.json"
    if not path.is_file():
        raise ValueError(f"Missing support span locator file: {path}")
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid support span locator JSON: {exc.msg}") from exc
    if not isinstance(rows, list):
        raise ValueError("Support span locator file must contain a JSON array")

    locators: dict[tuple[int, int], EvalSpanLocator] = {}
    for position, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Support span locator {position} must be an object")
        document_number = row.get("document_number")
        row_ordinal = row.get("row_ordinal")
        if isinstance(document_number, bool) or not isinstance(document_number, int) or document_number < 1:
            raise ValueError(f"Support span locator {position} has invalid document_number")
        if isinstance(row_ordinal, bool) or not isinstance(row_ordinal, int) or row_ordinal < 1:
            raise ValueError(f"Support span locator {position} has invalid row_ordinal")
        section_heading = row.get("section_heading")
        start_anchor = row.get("start_anchor")
        if (section_heading is None) == (start_anchor is None):
            raise ValueError(
                f"Support span locator {position} must provide exactly one of section_heading or start_anchor"
            )
        if section_heading is not None and (not isinstance(section_heading, str) or not section_heading.strip()):
            raise ValueError(f"Support span locator {position} has invalid section_heading")
        if start_anchor is not None and (not isinstance(start_anchor, str) or not start_anchor.strip()):
            raise ValueError(f"Support span locator {position} has invalid start_anchor")
        key = (document_number, row_ordinal)
        if key in locators:
            raise ValueError(f"Duplicate support span locator for document {document_number}, row {row_ordinal}")
        locators[key] = EvalSpanLocator(
            document_number=document_number,
            row_ordinal=row_ordinal,
            section_heading=section_heading,
            start_anchor=start_anchor,
        )
    return locators


def pair_eval_documents_and_supports(
    documents: dict[int, EvalSourceDocument],
    supports: dict[int, tuple[EvalSupportRow, ...]],
) -> tuple[tuple[EvalSourceDocument, tuple[EvalSupportRow, ...]], ...]:
    """
    Pair documents and supports by their shared numbered filename suffix.
    Args:
        documents: A dictionary mapping document numbers to 
            EvalSourceDocument instances.
        supports: A dictionary mapping support numbers to tuples of 
            EvalSupportRow instances.
    Returns:
        A tuple of (EvalSourceDocument, tuple[EvalSupportRow, ...]) pairs, 
        sorted by document number.
    Raises:
        ValueError: If there are unmatched documents or supports, or if 
        no pairs are found.
    """
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


def _find_unique_text(content: str, text: str, description: str, document: EvalSourceDocument) -> int:
    """
    Find the unique occurrence of a text string within the content.
    Args:
        content: The content to search within.
        text: The text to find.
        description: A description of the text being searched for, used 
            in error messages.
        document: The EvalSourceDocument containing the content.
    Returns:
        The starting index of the unique occurrence of the text.
    Raises:
        ValueError: If the text is not found or occurs multiple times.
    """
    first = content.find(text)
    if first == -1:
        raise ValueError(f"{description} is not found in {document.path.name}")
    if content.find(text, first + 1) != -1:
        raise ValueError(f"{description} occurs multiple times in {document.path.name}")
    return first


def _section_end(content: str, start: int, heading: str) -> int:
    """
    Find the end index of a section in the content.
    Args:
        content: The content to search within.
        start: The starting index of the section heading.
        heading: The section heading text.
    Returns:
        The ending index of the section.
    Raises:
        ValueError: If the section heading is not properly formatted.
    """
    level_match = re.match(r"^(#{1,6})\s", heading)
    if level_match is None:
        raise ValueError(f"Section heading must start with Markdown heading syntax: {heading!r}")
    level = len(level_match.group(1))
    next_heading = re.compile(r"^(#{1," + str(level) + r"})\s", re.MULTILINE).search(
        content, start + len(heading)
    )
    return next_heading.start() if next_heading else len(content)


def _find_support_span(
    document: EvalSourceDocument, row: EvalSupportRow, locator: EvalSpanLocator
) -> EvalSupportSpan:
    """
    Find the support span within a document based on the locator.
    Args:
        document: The EvalSourceDocument containing the content.
        row: The EvalSupportRow for which the span is being located.
        locator: The EvalSpanLocator specifying the location of the 
            support span.
    Returns:
        An EvalSupportSpan representing the located span.
    Raises:
        ValueError: If the support span cannot be uniquely located.
    """
    if locator.section_heading is not None:
        heading_pattern = re.compile(r"^" + re.escape(locator.section_heading) + r"\s*$", re.MULTILINE)
        matches = list(heading_pattern.finditer(document.content))
        if not matches:
            raise ValueError(f"Section heading {locator.section_heading!r} is not found in {document.path.name}")
        if len(matches) > 1:
            raise ValueError(f"Section heading {locator.section_heading!r} occurs multiple times in {document.path.name}")
        start = matches[0].start()
        end = _section_end(document.content, start, locator.section_heading)
    else:
        start = _find_unique_text(
            document.content,
            locator.start_anchor or "",
            f"Start anchor for support {row.ordinal} ({row.support_id!r})",
            document,
        )
        paragraph_end = document.content.find("\n\n", start)
        end = len(document.content) if paragraph_end == -1 else paragraph_end
    return EvalSupportSpan(
        evaluation_id=f"{document.document_id}:{row.support_id}:{row.ordinal}",
        support_id=row.support_id,
        document_id=document.document_id,
        query=row.query,
        support=row.support,
        start=start,
        end=end,
    )


def create_eval_corpus(root: str | Path | None = None) -> EvalCorpus:
    """
    Build a fully validated, in-memory evaluation corpus from suite files.
    Args:
        root: Optional root directory for the evaluation suite. If None,
            defaults to the directory of this file.
    Returns:
        An EvalCorpus containing documents, support spans, and examples.
    Raises:
        ValueError: If any part of the evaluation suite is invalid or 
        inconsistent.
    """
    pairs = pair_eval_documents_and_supports(load_eval_documents(root), load_eval_supports(root))
    locators = load_eval_span_locators(root)
    eval_documents: list[EvalDocument] = []
    source_documents: list[Document] = []
    support_spans: list[EvalSupportSpan] = []
    examples: list[EvalExample] = []

    for source, rows in pairs:
        spans = []
        for row in rows:
            locator = locators.get((source.number, row.ordinal))
            if locator is None:
                raise ValueError(
                    f"Missing support span locator for document {source.number}, row {row.ordinal}"
                )
            spans.append(_find_support_span(source, row, locator))
        spans = tuple(spans)
        eval_documents.append(
            EvalDocument(
                document_id=source.document_id,
                path=source.path,
                content=source.content,
                support_spans=spans,
            )
        )
        source_documents.append(
            Document(
                page_content=source.content,
                metadata={"eval_document_id": source.document_id, "source": str(source.path)},
            )
        )
        support_spans.extend(spans)
        examples.extend(
            EvalExample(
                evaluation_id=span.evaluation_id,
                query=span.query,
                support=span.support,
                document_id=span.document_id,
            )
            for span in spans
        )

    return EvalCorpus(
        documents=tuple(source_documents),
        eval_documents=tuple(eval_documents),
        support_spans=tuple(support_spans),
        examples=tuple(examples),
    )


def tag_chunks_with_evaluation_ids(
    chunks: Sequence[Document], corpus: EvalCorpus
) -> list[Document]:
    """
    Copy chunks and tag each one with IDs of the support spans it overlaps.

    Each chunk must provide ``eval_document_id`` and ``start_index`` metadata.
    ``end_index`` is optional; when absent, the end is calculated from its text.
    Args:
        chunks: A sequence of LangChain Documents representing retrieved 
            chunks.
        corpus: The EvalCorpus containing the support spans to match against.
    Returns:
        A list of new Documents with updated metadata including 
        ``evaluation_ids``.
    Raises:
        ValueError: If any chunk is missing required metadata or has 
        invalid values.
    """
    spans_by_document: dict[str, list[EvalSupportSpan]] = {}
    for span in corpus.support_spans:
        spans_by_document.setdefault(span.document_id, []).append(span)

    tagged: list[Document] = []
    for chunk in chunks:
        metadata = dict(chunk.metadata)
        document_id = metadata.get("eval_document_id")
        start = metadata.get("start_index")
        if not isinstance(document_id, str) or not isinstance(start, int):
            raise ValueError("Chunks must include string eval_document_id and integer start_index metadata")
        end = metadata.get("end_index", start + len(chunk.page_content))
        if not isinstance(end, int) or end < start:
            raise ValueError("Chunk end_index must be an integer greater than or equal to start_index")
        overlapping_ids = [
            span.evaluation_id
            for span in spans_by_document.get(document_id, [])
            if start < span.end and end > span.start
        ]
        if overlapping_ids:
            existing_ids = metadata.get("evaluation_ids", [])
            if not isinstance(existing_ids, list) or not all(isinstance(item, str) for item in existing_ids):
                raise ValueError("Chunk evaluation_ids metadata must be a list of strings")
            metadata["evaluation_ids"] = list(dict.fromkeys([*existing_ids, *overlapping_ids]))
        tagged.append(Document(page_content=chunk.page_content, metadata=metadata))
    return tagged


def make_invoke_runner(retriever: Any) -> EvalRunner:
    """
    Adapt a synchronous LangChain-style ``.invoke(query)`` retriever.
    Args:
        retriever: An object that provides a callable ``invoke(query)`` 
            method returning a sequence of LangChain Documents.
    Returns:
        An EvalRunner that wraps the retriever.
    Raises:
        ValueError: If the retriever does not provide a callable ``invoke(query)`` method"""
    invoke = getattr(retriever, "invoke", None)
    if not callable(invoke):
        raise ValueError("Retriever must provide a callable invoke(query) method")

    def runner(query: str) -> EvalExecutionResult:
        documents = invoke(query)
        if not isinstance(documents, (list, tuple)) or not all(
            isinstance(document, Document) for document in documents
        ):
            raise ValueError("Retriever invoke(query) must return a sequence of LangChain Documents")
        return EvalExecutionResult(answer=None, documents=documents)

    return runner


def _document_evaluation_ids(document: Document) -> tuple[str, ...]:
    """
    Document metadata must include evaluation_ids as a list of strings.
    Args:
        document: A LangChain Document to extract evaluation IDs from.
    Returns:
        A tuple of evaluation IDs.
    Raises:
        ValueError: If the evaluation_ids metadata is missing or invalid.
    """
    evaluation_ids = document.metadata.get("evaluation_ids", [])
    if not isinstance(evaluation_ids, list) or not all(isinstance(item, str) for item in evaluation_ids):
        raise ValueError("Retrieved document evaluation_ids metadata must be a list of strings")
    return tuple(evaluation_ids)


def calculate_hit_rate_at_k(results: Sequence[EvalQueryResult]) -> float:
    """
    Calculate the mean HitRate@k from already-scored query results.
    Args:
        results: A sequence of EvalQueryResult instances.
    Returns:
        The mean HitRate@k as a float.
    Raises:
        ValueError: If the results sequence is empty.
    """
    if not results:
        raise ValueError("Cannot calculate HitRate@k for an empty result set")
    return sum(result.hit_at_k for result in results) / len(results)


def calculate_mrr_at_k(results: Sequence[EvalQueryResult]) -> float:
    """
    Calculate the mean MRR@k from already-scored query results.
    Args:
        results: A sequence of EvalQueryResult instances.
    Returns:
        The mean MRR@k as a float.
    Raises:
        ValueError: If the results sequence is empty.
    """
    if not results:
        raise ValueError("Cannot calculate MRR@k for an empty result set")
    return sum(result.reciprocal_rank_at_k for result in results) / len(results)


def run_eval_suite(corpus: EvalCorpus, runner: EvalRunner, k: int) -> EvalRunResult:
    """Run every example and calculate HitRate@k and MRR@k from tagged chunks."""
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be at least 1")

    query_results: list[EvalQueryResult] = []
    for example in corpus.examples:
        execution = runner(example.query)
        if not isinstance(execution, EvalExecutionResult):
            raise ValueError("EvalRunner must return EvalExecutionResult")
        retrieved_ids = tuple(_document_evaluation_ids(document) for document in execution.documents)
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
                reference=example.support,
                retrieved_contexts=tuple(document.page_content for document in execution.documents),
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
