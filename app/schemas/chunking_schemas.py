from typing import Any, Literal

from sqlmodel import Field, SQLModel


class ChunkingOptions(SQLModel):
    chunker: Literal["recursive", "semantic", "hybrid"] = "recursive"
    chunk_size: int = Field(default=1000, ge=100, le=8000)
    chunk_overlap: int = Field(default=200, ge=0, le=2000)
    separators: list[str] | None = None
    breakpoint_threshold_type: str = "percentile"
    breakpoint_threshold_amount: int = Field(default=90, ge=1)
    buffer_size: int = Field(default=1, ge=0)
    preview: bool = False


class ChunkPreview(SQLModel):
    chunk_index: int
    content: str
    chunk_metadata: dict[str, Any] = Field(default_factory=dict)


class RawDocumentChunkResult(SQLModel):
    raw_document_id: int
    chunking_profile_id: int
    chunker: str
    preview: bool = False
    chunks_created: int = 0
    chunk_ids: list[int] = Field(default_factory=list)
    chunks: list[ChunkPreview] = Field(default_factory=list)


class CorpusChunkResult(SQLModel):
    corpus_id: int
    chunking_profile_id: int
    chunker: str
    preview: bool = False
    raw_documents: list[RawDocumentChunkResult] = Field(default_factory=list)
    chunks_created: int = 0
