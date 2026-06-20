from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING

from sqlalchemy import Column, DateTime as SQLAlchemyDateTime, JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .simulations import Simulation


class SimulationEvidenceLedger(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    simulation_id: int = Field(foreign_key="simulation.id", index=True)
    simulation: Optional["Simulation"] = Relationship()
    turn_index: int = Field(index=True, ge=0)
    agent_name: str = Field(index=True, min_length=1)
    sequence: int = Field(default=0, index=True, ge=0)
    visibility_level: str = Field(default="debug", index=True, min_length=1)
    pipeline: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    sources: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    quality_checks: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    model: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    token_usage: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    output_summary: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    raw_debug: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )
