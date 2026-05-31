from typing import Any, Optional, TYPE_CHECKING, TypedDict
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, JSON
from datetime import datetime, timezone

if TYPE_CHECKING:
    from .scenarios import Scenario
    from .users import User
    from .sessions import Session
    from .counterpart_personas import CounterPartPersonas
    from .corpus import Corpus


class NegotiationState(TypedDict, total=False):
    current_phase: str
    user_side: str
    data: dict[str, Any]


class SimulationMessage(TypedDict, total=False):
    role: str
    content: str
    timestamp: str
    metadata: dict[str, Any]


def default_negotiation_state() -> NegotiationState:
    return {}


def default_messages() -> list[SimulationMessage]:
    return []

class Simulation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, min_length=3, title="Simulation name")
    description: str | None = None
    status: str = Field(default="created", index=True, min_length=1, title="Simulation status")
    session_id: int | None = Field(default=None, foreign_key="session.id")
    session: Optional["Session"] = Relationship(back_populates="simulations")
    user_id_owner: int = Field(foreign_key="user.id")
    user_id_participant: int | None = Field(default=None, foreign_key="user.id")
    owner: "User" = Relationship(
        back_populates="simulations_owned",
        sa_relationship_kwargs={"foreign_keys": "[Simulation.user_id_owner]"},
)
    participant: Optional["User"] = Relationship(
        back_populates="simulations_participated",
        sa_relationship_kwargs={"foreign_keys": "[Simulation.user_id_participant]"},
)
    scenario_id: int | None = Field(default=None, foreign_key="scenario.id")  # the scenario being negotiated in this session
    scenario: Optional["Scenario"] = Relationship(back_populates="simulations")
    corpus_id: int = Field(foreign_key="corpus.id")
    corpus: "Corpus" = Relationship(back_populates="simulations")
    counter_part_side_persona_id: int | None = Field(default=None, foreign_key="counterpartpersonas.id")
    counter_part_side_persona: Optional["CounterPartPersonas"] = Relationship()
    user_side: str | None = Field(default=None, min_length=1, title="User side")  # "side_a" or "side_b", assigned at session start
    negotiation_state: NegotiationState = Field(default_factory=default_negotiation_state, sa_column=Column(JSON))
    messages: list[SimulationMessage] = Field(default_factory=default_messages, sa_column=Column(JSON))
    teacher_reviewed: bool = Field(default=False)  # whether a teacher has reviewed this session
    teacher_id: Optional[int] = Field(default=None, foreign_key="user.id")  # the teacher who reviewed the session
    teacher: Optional["User"] = Relationship(
        back_populates="simulations_reviewed",
        sa_relationship_kwargs={"foreign_keys": "[Simulation.teacher_id]"},
    )
    teacher_feedback: str | None = Field(default=None, min_length=1, title="Teacher feedback")  # optional feedback from the teacher after review
    reviewed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
