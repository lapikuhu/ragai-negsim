from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime as SQLAlchemyDateTime, JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .corpus_indices import CorpusIndex
    from .knowledge_graph_build_jobs import KnowledgeGraphBuildJob
    from .rag_profiles import RagProfile


class KnowledgeGraphIndex(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, min_length=3)
    corpus_index_id: int = Field(foreign_key="corpusindex.id", index=True)
    build_config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="created", index=True, min_length=1)
    active_generation: str | None = Field(default=None, index=True)
    latest_build_error: str | None = None
    locked_at: datetime | None = Field(
        default=None,
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=True),
    )
    built_at: datetime | None = Field(
        default=None,
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )
    corpus_index: "CorpusIndex" = Relationship(back_populates="knowledge_graph_indices")
    build_jobs: list["KnowledgeGraphBuildJob"] = Relationship(
        back_populates="knowledge_graph_index"
    )
    rag_profiles: list["RagProfile"] = Relationship(
        back_populates="knowledge_graph_index"
    )

