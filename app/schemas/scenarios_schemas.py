from sqlmodel import Field, SQLModel


class ScenarioBase(SQLModel):
    name: str = Field(min_length=3, title="Scenario name")
    description: str | None = None


class ScenarioCreate(ScenarioBase):
    pass


class ScenarioRead(ScenarioBase):
    id: int


class ScenarioUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="Scenario name")
    description: str | None = None