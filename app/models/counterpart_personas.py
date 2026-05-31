from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .simulations import Simulation
    from .users import User


class CounterPartPersonas(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, min_length=3, title="Counterpart persona name")
    description: str | None = None
    created_by_user_id: int = Field(foreign_key="user.id")
    created_by_user: "User" = Relationship(
        back_populates="counterpart_personas_created",
        sa_relationship_kwargs={"foreign_keys": "[CounterPartPersonas.created_by_user_id]"},
    )
    last_edit_by_user_id: int | None = Field(default=None, foreign_key="user.id")
    last_edit_by_user: Optional["User"] = Relationship(
        back_populates="counterpart_personas_last_edited",
        sa_relationship_kwargs={"foreign_keys": "[CounterPartPersonas.last_edit_by_user_id]"},
    )
    simulations: list["Simulation"] = Relationship(back_populates="counter_part_side_persona")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
