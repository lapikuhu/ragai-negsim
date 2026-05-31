from sqlmodel import Field, SQLModel


class CounterPartPersonas(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, min_length=3, title="Counterpart persona name")
    description: str | None = None
