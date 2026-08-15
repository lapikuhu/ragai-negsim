from datetime import datetime, timezone
from typing import TYPE_CHECKING, ClassVar, Optional

from sqlalchemy import CheckConstraint, Column, DateTime as SQLAlchemyDateTime, JSON, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .chunking_profiles import ChunkingProfile
    from .corpus import Corpus
    from .document_chunks import DocumentChunk


class CorpusChunkSetDocumentChunkLink(SQLModel, table=True):
    __tablename__: ClassVar[str] = "corpuschunksetdocumentchunklink"

    corpus_chunk_set_id: int = Field(
        foreign_key="corpuschunkset.id",
        primary_key=True,
        ondelete="CASCADE",
    )
    document_chunk_id: int = Field(
        foreign_key="documentchunk.id",
        primary_key=True,
        ondelete="RESTRICT",
    )


class CorpusChunkSet(SQLModel, table=True):
    """
    Represents a set of chunks for a specific corpus. The chunks are
    referenced. Corpora can have multiple chunk sets.
    The first class object carries also metadata.
    """
    __tablename__: ClassVar[str] = "corpuschunkset"
    __table_args__ = (
        UniqueConstraint("corpus_id", "name", name="uq_corpus_chunk_set_corpus_name"),
        CheckConstraint("revision >= 1", name="ck_corpus_chunk_set_revision_positive"),
    )

    id: int | None = Field(default=None, primary_key=True)
    corpus_id: int = Field(foreign_key="corpus.id", index=True, ondelete="CASCADE")
    name: str = Field(min_length=3)
    chunking_profile_id: int | None = Field(
        default=None,
        foreign_key="chunkingprofile.id",
        index=True,
        ondelete="SET NULL",
    )
    chunking_profile_name: str = Field(min_length=1)
    chunking_strategy: str = Field(min_length=1)
    chunking_config: dict = Field(sa_column=Column(JSON, nullable=False))
    revision: int = Field(default=1, ge=1)
    document_chunk_ids_checksum: str = Field(min_length=64, max_length=64)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )

    corpus: "Corpus" = Relationship(back_populates="chunk_sets")
    chunking_profile: Optional["ChunkingProfile"] = Relationship(
        back_populates="corpus_chunk_sets"
    )
    document_chunks: list["DocumentChunk"] = Relationship(
        back_populates="corpus_chunk_sets",
        link_model=CorpusChunkSetDocumentChunkLink,
    )
