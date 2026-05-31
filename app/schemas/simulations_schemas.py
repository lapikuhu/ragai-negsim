from datetime import datetime
from typing import Any, Literal

from sqlmodel import Field, SQLModel


SimulationStatus = Literal["created", "active", "paused", "completed", "cancelled", "failed"]
SimulationSide = Literal["side_a", "side_b"]


class NegotiationStateSchema(SQLModel):
    current_phase: str | None = None
    user_side: SimulationSide | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class SimulationMessageSchema(SQLModel):
    role: str = Field(min_length=1)
    content: str = Field(min_length=1)
    timestamp: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationBase(SQLModel):
    name: str = Field(min_length=3, title="Simulation name")
    description: str | None = None


class SimulationCreate(SimulationBase):
    user_id_owner: int
    corpus_id: int
    session_id: int | None = None
    user_id_participant: int | None = None
    scenario_id: int | None = None
    counter_part_side_persona_id: int | None = None
    user_side: SimulationSide | None = None


class SimulationRead(SimulationBase):
    id: int
    status: str
    session_id: int | None = None
    user_id_owner: int
    user_id_participant: int | None = None
    scenario_id: int | None = None
    corpus_id: int
    counter_part_side_persona_id: int | None = None
    user_side: str | None = None
    teacher_reviewed: bool
    teacher_id: int | None = None
    teacher_feedback: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    last_updated: datetime


class SimulationReadWithState(SimulationRead):
    negotiation_state: NegotiationStateSchema = Field(default_factory=NegotiationStateSchema)
    messages: list[SimulationMessageSchema] = Field(default_factory=list)


class SimulationUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="Simulation name")
    description: str | None = None
    status: SimulationStatus | None = None
    session_id: int | None = None
    user_id_participant: int | None = None
    scenario_id: int | None = None
    counter_part_side_persona_id: int | None = None
    user_side: SimulationSide | None = None
    negotiation_state: NegotiationStateSchema | None = None
    messages: list[SimulationMessageSchema] | None = None


class SimulationStatusUpdate(SQLModel):
    status: SimulationStatus


class SimulationMessageAppend(SQLModel):
    message: SimulationMessageSchema


class SimulationMessagesReplace(SQLModel):
    messages: list[SimulationMessageSchema] = Field(default_factory=list)


class SimulationNegotiationStateUpdate(SQLModel):
    negotiation_state: NegotiationStateSchema


class SimulationTeacherReview(SQLModel):
    teacher_id: int
    teacher_feedback: str | None = None
    teacher_reviewed: bool = True
    reviewed_at: datetime | None = None


class SimulationReadWithIds(SimulationRead):
    # Mostly redundant because SimulationRead already exposes foreign keys,
    # but useful if you want an explicit relationship-summary convention.
    related_user_ids: list[int] = Field(default_factory=list)