from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime as SQLAlchemyDateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .corpus_indices import CorpusIndex
    from .document_chunks import DocumentChunk


class IndexedChunk(SQLModel, table=True):
    corpus_index_id: int = Field(foreign_key="corpusindex.id", primary_key=True)
    document_chunk_id: int = Field(foreign_key="documentchunk.id", primary_key=True)
    external_vector_id: str | None = Field(default=None, min_length=1)
    corpus_index: "CorpusIndex" = Relationship(back_populates="indexed_chunks")
    document_chunk: "DocumentChunk" = Relationship(back_populates="indexed_chunks")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )
