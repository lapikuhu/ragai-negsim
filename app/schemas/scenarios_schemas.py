from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class ScenarioAuthoringBase(SQLModel):
    name: str = Field(min_length=3, title="Scenario name")
    description: str | None = None
    public_context: dict[str, Any] = Field(default_factory=dict)
    side_a_private_context: dict[str, Any] = Field(default_factory=dict)
    side_b_private_context: dict[str, Any] = Field(default_factory=dict)
    side_a_summary: str = ""
    side_b_summary: str = ""


class ScenarioPublicBase(SQLModel):
    name: str = Field(min_length=3, title="Scenario name")
    description: str | None = None
    public_context: dict[str, Any] = Field(default_factory=dict)


class ScenarioCreateRequest(ScenarioAuthoringBase):
    pass


class ScenarioCreate(ScenarioAuthoringBase):
    created_by_user_id: int


class ScenarioAuthoringRead(ScenarioAuthoringBase):
    id: int
    created_by_user_id: int
    last_edit_by_user_id: int | None = None
    created_at: datetime
    last_updated: datetime


class ScenarioPublicRead(ScenarioPublicBase):
    id: int
    created_by_user_id: int
    last_edit_by_user_id: int | None = None
    created_at: datetime
    last_updated: datetime


class ScenarioUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="Scenario name")
    description: str | None = None
    public_context: dict[str, Any] | None = None
    side_a_private_context: dict[str, Any] | None = None
    side_b_private_context: dict[str, Any] | None = None
    side_a_summary: str | None = None
    side_b_summary: str | None = None
    last_edit_by_user_id: int | None = None


class ScenarioUpdateRequest(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="Scenario name")
    description: str | None = None
    public_context: dict[str, Any] | None = None
    side_a_private_context: dict[str, Any] | None = None
    side_b_private_context: dict[str, Any] | None = None
    side_a_summary: str | None = None
    side_b_summary: str | None = None


class ScenarioCopyRequest(SQLModel):
    name: str = Field(min_length=3, title="Scenario name")
    description: str | None = None


class ScenarioCopy(SQLModel):
    name: str = Field(min_length=3, title="Scenario name")
    description: str | None = None
    created_by_user_id: int


class ScenarioContextGenerateRequest(SQLModel):
    name: str = Field(min_length=3, title="Scenario name")
    description: str = Field(min_length=10, title="Scenario description")


class ScenarioContextGenerateResponse(SQLModel):
    public_context: dict[str, Any] = Field(default_factory=dict)
    side_a_private_context: dict[str, Any] = Field(default_factory=dict)
    side_b_private_context: dict[str, Any] = Field(default_factory=dict)
    side_a_summary: str = ""
    side_b_summary: str = ""


class ScenarioContextGenerationModel(BaseModel):
    public_context: dict[str, Any] = Field(default_factory=dict)
    side_a_private_context: dict[str, Any] = Field(default_factory=dict)
    side_b_private_context: dict[str, Any] = Field(default_factory=dict)


class ScenarioSummaryGenerationModel(BaseModel):
    side_a_summary: str = ""
    side_b_summary: str = ""


class ScenarioAuthoringReadWithIds(ScenarioAuthoringRead):
    simulation_ids: list[int] = Field(default_factory=list)


class ScenarioPublicReadWithIds(ScenarioPublicRead):
    simulation_ids: list[int] = Field(default_factory=list)
