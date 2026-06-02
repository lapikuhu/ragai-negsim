from datetime import datetime

from sqlmodel import Field, SQLModel


class RawDocumentBase(SQLModel):
	name: str = Field(min_length=3, title="Raw document name")
	description: str | None = None
	path: str = Field(min_length=1, title="Raw document path")


class RawDocumentCreate(RawDocumentBase):
	corpus_ids: list[int] = Field(default_factory=list)


class RawDocumentCreateDb(RawDocumentCreate):
	uploaded_by_user_id: int


class RawDocumentRead(RawDocumentBase):
	id: int
	uploaded_at: datetime
	uploaded_by_user_id: int
	parsed_at: datetime | None = None


class RawDocumentUpdate(SQLModel):
	name: str | None = Field(default=None, min_length=3, title="Raw document name")
	description: str | None = None
	path: str | None = Field(default=None, min_length=1, title="Raw document path")


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
