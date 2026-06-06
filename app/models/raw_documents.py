from typing import TYPE_CHECKING
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime as SQLAlchemyDateTime, Text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .corpus import Corpus
    from .document_chunks import DocumentChunk
    from .users import User


class CorpusRawDocumentLink(SQLModel, table=True):
    corpus_id: int | None = Field(default=None, foreign_key="corpus.id", primary_key=True)
    raw_document_id: int | None = Field(default=None, foreign_key="rawdocument.id", primary_key=True)


class RawDocument(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, min_length=3, title="Raw document name")         # e.g. "employee_handbook"
    description: str | None = None
    source_path: str = Field(index=True, unique=True, min_length=1, title="Raw document source path")
    source_hash: str | None = Field(default=None, min_length=1, title="Raw document source hash")
    source_size: int | None = Field(default=None, ge=0, title="Raw document source size")
    source_mtime: datetime | None = Field(
        default=None,
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=True),
    )
    source_status: str = Field(default="unverified", min_length=1, title="Raw document source status")
    parsed_content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    parsed_at: datetime | None = Field(
        default=None,
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=True),
    )
    uploaded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )
    uploaded_by_user_id: int = Field(foreign_key="user.id")
    uploaded_by: "User" = Relationship(back_populates="raw_documents_uploaded")
    corpora: list["Corpus"] = Relationship(
        back_populates="raw_documents",
        link_model=CorpusRawDocumentLink,
    )
    document_chunks: list["DocumentChunk"] = Relationship(back_populates="raw_document")
