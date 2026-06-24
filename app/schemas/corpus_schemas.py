from datetime import datetime

from sqlmodel import Field, SQLModel


class CorpusBase(SQLModel):
	name: str = Field(min_length=3, title="Corpus name")
	description: str | None = None


class CorpusCreate(CorpusBase):
    raw_document_ids: list[int] = Field(default_factory=list)


class CorpusRead(CorpusBase):
	id: int
	created_by_user_id: int
	created_by_username: str | None = None
	last_edit_by_user_id: int | None = None
	last_edit_by_username: str | None = None
	created_at: datetime


class CorpusUpdate(SQLModel):
	name: str | None = Field(default=None, min_length=3, title="Corpus name")
	description: str | None = None
	last_edit_by_user_id: int


class CorpusReadWithIds(CorpusRead):
	raw_document_ids: list[int] = Field(default_factory=list)
	corpus_index_ids: list[int] = Field(default_factory=list)
	simulation_ids: list[int] = Field(default_factory=list)
