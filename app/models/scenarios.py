from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime as SQLAlchemyDateTime
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .simulations import Simulation
    from .users import User

class Scenario(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)         # e.g. "salary_negotiation"
    description: str | None = None
    created_by_user_id: int = Field(foreign_key="user.id")
    created_by_user: "User" = Relationship(
        back_populates="scenarios_created",
        sa_relationship_kwargs={"foreign_keys": "[Scenario.created_by_user_id]"},
    )
    last_edit_by_user_id: int | None = Field(default=None, foreign_key="user.id")
    last_edit_by_user: Optional["User"] = Relationship(
        back_populates="scenarios_last_edited",
        sa_relationship_kwargs={"foreign_keys": "[Scenario.last_edit_by_user_id]"},
    )
    simulations: list["Simulation"] = Relationship(back_populates="scenario")  # simulations that have used this scenario
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )