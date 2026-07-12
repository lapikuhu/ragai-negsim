from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime as SQLAlchemyDateTime, JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .knowledge_graph_indices import KnowledgeGraphIndex


class KnowledgeGraphBuildJob(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    knowledge_graph_index_id: int = Field(
        foreign_key="knowledgegraphindex.id",
        index=True,
    )
    status: str = Field(default="queued", index=True, min_length=1)
    stage: str = Field(default="validating", index=True, min_length=1)
    build_config_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON))
    chunk_ids_snapshot: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    candidate_generation: str = Field(index=True, min_length=1)
    total_documents: int = Field(default=0, ge=0)
    processed_documents: int = Field(default=0, ge=0)
    current_raw_document_id: int | None = Field(default=None, foreign_key="rawdocument.id")
    current_document_label: str | None = None
    total_chunks: int = Field(default=0, ge=0)
    processed_chunks: int = Field(default=0, ge=0)
    node_count: int = Field(default=0, ge=0)
    relationship_count: int = Field(default=0, ge=0)
    cancel_requested: bool = Field(default=False)
    failure_detail: str | None = None
    queued_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )
    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=True),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=True),
    )
    knowledge_graph_index: "KnowledgeGraphIndex" = Relationship(
        back_populates="build_jobs"
    )
