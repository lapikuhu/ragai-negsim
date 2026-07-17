"""Shared data models for deterministic and LLM-based evaluation."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document


@dataclass(frozen=True)
class EvalSourceDocument:
    """
    Represents a source document used in evaluation.
    """
    document_id: str
    number: int
    path: Path
    content: str


@dataclass(frozen=True)
class EvalSupportRow:
    """
    Represents a support row used in evaluation.
    """
    evaluation_id: str
    category: str
    answerable: bool
    query: str
    reference_answer: str
    ordinal: int
    bridge_entity: str | None = None


@dataclass(frozen=True)
class EvalSpanLocator:
    """
    Represents a span locator within a document used in evaluation.
    """
    evaluation_id: str
    document_number: int
    quote: str


@dataclass(frozen=True)
class EvalSupportSpan:
    """
    Represents a support span used in evaluation.
    """
    evaluation_id: str
    support_id: str
    document_id: str
    query: str
    support: str
    start: int
    end: int


@dataclass(frozen=True)
class EvalDocument:
    """
    Represents a document used in evaluation.
    """
    document_id: str
    path: Path
    content: str
    support_spans: tuple[EvalSupportSpan, ...]


@dataclass(frozen=True)
class EvalExample:
    """
    Represents an evaluation example.
    """
    evaluation_id: str
    query: str
    reference_answer: str
    legacy_document_id: str = ""
    category: str = "direct_retrieval"
    answerable: bool = True
    support_spans: tuple[EvalSupportSpan, ...] = ()
    bridge_entity: str | None = None

    @property
    def support(self) -> str:
        """Backward-compatible name used by the current evaluation runtime."""
        return self.reference_answer

    @property
    def document_id(self) -> str:
        """Return the first evidence document for legacy single-span consumers."""
        return (
            self.support_spans[0].document_id
            if self.support_spans
            else self.legacy_document_id
        )


@dataclass(frozen=True)
class EvalCorpus:
    """
    Represents a corpus used in evaluation.
    """
    documents: tuple[Document, ...]
    eval_documents: tuple[EvalDocument, ...]
    support_spans: tuple[EvalSupportSpan, ...]
    examples: tuple[EvalExample, ...]
    suite_version: str = ""
    suite_content_hash: str = ""


@dataclass(frozen=True)
class EvalExecutionResult:
    """
    Represents the result of an evaluation execution.
    """
    answer: str | None
    documents: Sequence[Document]


@dataclass(frozen=True)
class EvalQueryResult:
    """
    Represents the result of an evaluation query.
    """
    evaluation_id: str
    query: str
    answer: str | None
    reference: str
    retrieved_contexts: tuple[str, ...]
    retrieved_evaluation_ids: tuple[tuple[str, ...], ...]
    first_relevant_rank: int | None
    hit_at_k: bool
    reciprocal_rank_at_k: float


@dataclass(frozen=True)
class EvalRunResult:
    """
    Represents the result of an evaluation run.
    """
    k: int
    results: tuple[EvalQueryResult, ...]
    hit_rate_at_k: float
    mrr_at_k: float


EvalRunner = Callable[[str], EvalExecutionResult]


@dataclass(frozen=True)
class RagasQueryResult:
    """
    Represents the result of a Ragas query.
    """
    evaluation_id: str
    metric_scores: Mapping[str, float]


@dataclass(frozen=True)
class RagasRunResult:
    """
    Represents the result of a Ragas run.
    """
    results: tuple[RagasQueryResult, ...]
    metric_means: Mapping[str, float]
