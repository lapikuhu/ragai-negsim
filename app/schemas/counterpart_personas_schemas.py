from sqlmodel import Field, SQLModel


class CounterpartPersonaBase(SQLModel):
    name: str = Field(min_length=3, title="Counterpart persona name")
    description: str | None = None


class CounterpartPersonaCreate(CounterpartPersonaBase):
    pass


class CounterpartPersonaRead(CounterpartPersonaBase):
    id: int


class CounterpartPersonaUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="Counterpart persona name")
    description: str | None = None


class CounterpartPersonaReadWithIds(CounterpartPersonaRead):
    simulation_ids: list[int] = Field(default_factory=list)