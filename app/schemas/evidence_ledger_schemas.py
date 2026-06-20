from datetime import datetime
from typing import Any, Literal

from sqlmodel import Field, SQLModel


EvidenceVisibilityLevel = Literal["learner", "teacher", "debug"]


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
