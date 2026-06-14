from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime as SQLAlchemyDateTime, JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .knowledge_graph_indices import KnowledgeGraphIndex
    from .simulations import Simulation
    from .users import User


class RagProfile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, min_length=3, title="RAG profile name")
    strategy: str = Field(min_length=1, title="RAG strategy")
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    knowledge_graph_index_id: int | None = Field(
        default=None,
        foreign_key="knowledgegraphindex.id",
        index=True,
    )
    knowledge_graph_index: Optional["KnowledgeGraphIndex"] = Relationship(
        back_populates="rag_profiles"
    )
    created_by_user_id: int = Field(foreign_key="user.id")
    created_by_user: "User" = Relationship(
        back_populates="rag_profiles_created",
        sa_relationship_kwargs={"foreign_keys": "[RagProfile.created_by_user_id]"},
    )
    last_edit_by_user_id: int | None = Field(default=None, foreign_key="user.id")
    last_edit_by_user: Optional["User"] = Relationship(
        back_populates="rag_profiles_last_edited",
        sa_relationship_kwargs={"foreign_keys": "[RagProfile.last_edit_by_user_id]"},
    )
    simulations: list["Simulation"] = Relationship(back_populates="rag_profile")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )
