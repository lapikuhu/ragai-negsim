"""Shared data models for deterministic and LLM-based evaluation."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document


@dataclass(frozen=True)
class EvalSourceDocument:
    document_id: str
    number: int
    path: Path
    content: str


@dataclass(frozen=True)
class EvalSupportRow:
    support_id: str
    query: str
    support: str
    ordinal: int


@dataclass(frozen=True)
class EvalSpanLocator:
    document_number: int
    row_ordinal: int
    section_heading: str | None = None
    start_anchor: str | None = None


@dataclass(frozen=True)
class EvalSupportSpan:
    evaluation_id: str
    support_id: str
    document_id: str
    query: str
    support: str
    start: int
    end: int


@dataclass(frozen=True)
class EvalDocument:
    document_id: str
    path: Path
    content: str
    support_spans: tuple[EvalSupportSpan, ...]


@dataclass(frozen=True)
class EvalExample:
    evaluation_id: str
    query: str
    support: str
    document_id: str


@dataclass(frozen=True)
class EvalCorpus:
    documents: tuple[Document, ...]
    eval_documents: tuple[EvalDocument, ...]
    support_spans: tuple[EvalSupportSpan, ...]
    examples: tuple[EvalExample, ...]


@dataclass(frozen=True)
class EvalExecutionResult:
    answer: str | None
    documents: Sequence[Document]


@dataclass(frozen=True)
class EvalQueryResult:
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
    k: int
    results: tuple[EvalQueryResult, ...]
    hit_rate_at_k: float
    mrr_at_k: float


EvalRunner = Callable[[str], EvalExecutionResult]


@dataclass(frozen=True)
class RagasQueryResult:
    evaluation_id: str
    metric_scores: Mapping[str, float]


@dataclass(frozen=True)
class RagasRunResult:
    results: tuple[RagasQueryResult, ...]
    metric_means: Mapping[str, float]
