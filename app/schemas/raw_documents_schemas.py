from datetime import datetime

from sqlmodel import Field, SQLModel


class RawDocumentBase(SQLModel):
	name: str = Field(min_length=3, title="Raw document name")
	description: str | None = None
	path: str = Field(min_length=1, title="Raw document path")


class RawDocumentCreate(RawDocumentBase):
	uploaded_by_user_id: int
	corpus_ids: list[int] = Field(default_factory=list)


class RawDocumentRead(RawDocumentBase):
	id: int
	uploaded_at: datetime
	uploaded_by_user_id: int


class RawDocumentUpdate(SQLModel):
	name: str | None = Field(default=None, min_length=3, title="Raw document name")
	description: str | None = None
	path: str | None = Field(default=None, min_length=1, title="Raw document path")


class RawDocumentReadWithIds(RawDocumentRead):
	corpus_ids: list[int] = Field(default_factory=list)
	document_chunk_ids: list[int] = Field(default_factory=list)


class CorpusRawDocumentLinkCreate(SQLModel):
	corpus_id: int
	raw_document_id: int


class CorpusRawDocumentLinkRead(SQLModel):
	corpus_id: int
	raw_document_id: int


class CorpusRawDocumentLinkDelete(SQLModel):
	corpus_id: int
	raw_document_id: int
