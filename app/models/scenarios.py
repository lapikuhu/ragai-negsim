from typing import TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship
if TYPE_CHECKING:
    from .simulations import Simulation

class Scenario(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)         # e.g. "salary_negotiation"
    description: str | None = None
    simulations: list["Simulation"] = Relationship(back_populates="scenario")  # simulations that have used this scenario