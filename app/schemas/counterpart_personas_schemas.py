from datetime import datetime

from sqlmodel import Field, SQLModel


class CounterpartPersonaBase(SQLModel):
    name: str = Field(min_length=3, title="Counterpart persona name")
    description: str | None = None


class CounterpartPersonaCreate(CounterpartPersonaBase):
    created_by_user_id: int


class CounterpartPersonaRead(CounterpartPersonaBase):
    id: int
    created_by_user_id: int
    last_edit_by_user_id: int | None = None
    created_at: datetime
    last_updated: datetime


class CounterpartPersonaUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="Counterpart persona name")
    description: str | None = None
    last_edit_by_user_id: int | None = None


class CounterpartPersonaCopy(SQLModel):
    name: str = Field(min_length=3, title="Counterpart persona name")
    description: str | None = None


class CounterpartPersonaReadWithIds(CounterpartPersonaRead):
    simulation_ids: list[int] = Field(default_factory=list)