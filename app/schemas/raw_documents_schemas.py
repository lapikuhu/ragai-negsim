from datetime import datetime
from typing import Literal

from sqlmodel import Field, SQLModel

from app.schemas.corpus_schemas import CorpusSummaryRead

RawDocumentSourceStatus = Literal["available", "missing", "changed", "unverified", "error"]


class RawDocumentSourceMetadata(SQLModel):
    source_hash: str | None = None
    source_size: int | None = Field(default=None, ge=0)
    source_mtime: datetime | None = None
    source_status: RawDocumentSourceStatus = "unverified"


class RawDocumentBase(SQLModel):
    name: str = Field(min_length=3, title="Raw document name")
    description: str | None = None
    source_path: str = Field(min_length=1, title="Raw document source path")


class RawDocumentCreate(RawDocumentBase, RawDocumentSourceMetadata):
    corpus_ids: list[int] = Field(default_factory=list)


class RawDocumentCreateDb(RawDocumentCreate):
    uploaded_by_user_id: int


class RawDocumentRead(RawDocumentBase, RawDocumentSourceMetadata):
    id: int
    uploaded_at: datetime
    uploaded_by_user_id: int
    uploaded_by_username: str | None = None
    parsed_at: datetime | None = None


class RawDocumentDetailRead(RawDocumentBase, RawDocumentSourceMetadata):
    id: int
    uploaded_at: datetime
    uploaded_by_user_id: int
    uploaded_by_username: str | None = None
    associated_corpora: list[CorpusSummaryRead] = Field(default_factory=list)


class RawDocumentUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="Raw document name")
    description: str | None = None
    source_path: str | None = Field(default=None, min_length=1, title="Raw document source path")
    source_hash: str | None = Field(default=None, min_length=1)
    source_size: int | None = Field(default=None, ge=0)
    source_mtime: datetime | None = None
    source_status: RawDocumentSourceStatus | None = None


class RawDocumentReadWithIds(RawDocumentRead):
    corpus_ids: list[int] = Field(default_factory=list)
    document_chunk_ids: list[int] = Field(default_factory=list)


class RawDocumentReadWithParsedContent(RawDocumentRead):
    parsed_content: str | None = None


class CorpusRawDocumentLinkCreate(SQLModel):
    corpus_id: int
    raw_document_id: int


class CorpusRawDocumentLinkRead(SQLModel):
    corpus_id: int
    raw_document_id: int


class CorpusRawDocumentLinkDelete(SQLModel):
    corpus_id: int
    raw_document_id: int
