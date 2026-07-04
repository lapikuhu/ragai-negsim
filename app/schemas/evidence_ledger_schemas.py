from datetime import datetime
from typing import Any, Literal

from sqlmodel import Field, SQLModel


EvidenceVisibilityLevel = Literal["learner", "teacher", "debug"]


class SourceCard(SQLModel):
    rank: int | None = None
    raw_document_id: int | None = None
    raw_document_name: str | None = None
    document_chunk_id: int | None = None
    chunk_index: int | None = None
    source: str | None = None
    score: float | None = None
    rerank_score: float | None = None
    retrieval_strategy: str | None = None
    retrieval_mode: str | None = None
    graph_id: int | str | None = None
    graph_generation: int | str | None = None
    evidence_path: str | None = None
    excerpt: str | None = None


class SimulationEvidenceLedgerBase(SQLModel):
    simulation_id: int
    turn_index: int = Field(ge=0)
    agent_name: str = Field(min_length=1)
    sequence: int = Field(default=0, ge=0)
    visibility_level: EvidenceVisibilityLevel = "debug"
    pipeline: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    quality_checks: list[dict[str, Any]] = Field(default_factory=list)
    model: dict[str, Any] = Field(default_factory=dict)
    token_usage: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    raw_debug: dict[str, Any] = Field(default_factory=dict)


class SimulationEvidenceLedgerCreate(SimulationEvidenceLedgerBase):
    pass


class SimulationEvidenceLedgerRead(SimulationEvidenceLedgerBase):
    id: int
    created_at: datetime
