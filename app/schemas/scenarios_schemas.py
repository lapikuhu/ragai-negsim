from datetime import datetime

from sqlmodel import Field, SQLModel


class ScenarioBase(SQLModel):
    name: str = Field(min_length=3, title="Scenario name")
    description: str | None = None


class ScenarioCreateRequest(ScenarioBase):
    pass


class ScenarioCreate(ScenarioBase):
    created_by_user_id: int


class ScenarioRead(ScenarioBase):
    id: int
    created_by_user_id: int
    last_edit_by_user_id: int | None = None
    created_at: datetime
    last_updated: datetime


class ScenarioUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="Scenario name")
    description: str | None = None
    last_edit_by_user_id: int | None = None


class ScenarioUpdateRequest(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="Scenario name")
    description: str | None = None


class ScenarioCopyRequest(SQLModel):
    name: str = Field(min_length=3, title="Scenario name")
    description: str | None = None


class ScenarioCopy(SQLModel):
    name: str = Field(min_length=3, title="Scenario name")
    description: str | None = None
    created_by_user_id: int


class ScenarioReadWithIds(ScenarioRead):
    simulation_ids: list[int] = Field(default_factory=list)
