from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel


class KnowledgeGraphBuildJobCreate(SQLModel):
    knowledge_graph_index_id: int
    build_config_snapshot: dict[str, Any] = Field(default_factory=dict)
    chunk_ids_snapshot: list[int] = Field(default_factory=list)
    candidate_generation: str = Field(min_length=1)
    total_documents: int = Field(default=0, ge=0)
    processed_documents: int = Field(default=0, ge=0)
    current_raw_document_id: int | None = None
    current_document_label: str | None = None
    status: str = "queued"
    stage: str = "validating"
    total_chunks: int = Field(default=0, ge=0)


class KnowledgeGraphBuildJobRead(KnowledgeGraphBuildJobCreate):
    id: int
    processed_chunks: int
    node_count: int = Field(default=0, ge=0)
    relationship_count: int = Field(default=0, ge=0)
    cancel_requested: bool
    failure_detail: str | None = None
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
