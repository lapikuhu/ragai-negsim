from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel


class RagProfileBase(SQLModel):
    name: str = Field(min_length=3, title="RAG profile name")
    strategy: str = Field(min_length=1, title="RAG strategy")
    config: dict[str, Any] = Field(default_factory=dict)
    knowledge_graph_index_id: int | None = None


class RagProfileCreateRequest(RagProfileBase):
    pass


class RagProfileCreate(RagProfileBase):
    created_by_user_id: int


class RagProfileRead(RagProfileBase):
    id: int
    created_by_user_id: int
    last_edit_by_user_id: int | None = None
    created_at: datetime
    last_updated: datetime


class RagProfileUpdateRequest(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="RAG profile name")
    strategy: str | None = Field(default=None, min_length=1, title="RAG strategy")
    config: dict[str, Any] | None = None
    knowledge_graph_index_id: int | None = None


class RagProfileUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="RAG profile name")
    strategy: str | None = Field(default=None, min_length=1, title="RAG strategy")
    config: dict[str, Any] | None = None
    knowledge_graph_index_id: int | None = None
    last_edit_by_user_id: int | None = None


class RagProfileCopy(SQLModel):
    name: str = Field(min_length=3, title="RAG profile name")
    strategy: str | None = Field(default=None, min_length=1, title="RAG strategy")
    config: dict[str, Any] | None = None
    knowledge_graph_index_id: int | None = None


class RagProfileReadWithIds(RagProfileRead):
    simulation_ids: list[int] = Field(default_factory=list)
