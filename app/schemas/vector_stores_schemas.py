from datetime import datetime
from typing import Any, Literal

from sqlmodel import Field, SQLModel

VectorStoreBackend = Literal["chroma", "faiss", "pgvector"]

class VectorStoreBase(SQLModel):
    name: str = Field(min_length=3, title="Vector store name")
    backend: VectorStoreBackend = Field(title="Vector store backend")
    connection_uri: str | None = None
    collection_name: str | None = None
    table_name: str | None = None
    path: str | None = None
    store_metadata: dict[str, Any] = Field(default_factory=dict)

class VectorStoreCreate(VectorStoreBase):
    pass

class VectorStoreRead(VectorStoreBase):
    id: int
    created_at: datetime
    last_updated: datetime

class VectorStoreUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="Vector store name")
    backend: VectorStoreBackend | None = None
    connection_uri: str | None = None
    collection_name: str | None = None
    table_name: str | None = None
    path: str | None = None
    store_metadata: dict[str, Any] | None = None

class VectorStoreReadWithIds(VectorStoreRead):
    corpus_index_ids: list[int] = Field(default_factory=list)

class VectorStoreConnectionUpdate(SQLModel):
    connection_uri: str | None = None
    collection_name: str | None = None
    table_name: str | None = None
    path: str | None = None
    store_metadata: dict[str, Any] | None = None