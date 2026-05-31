from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from .raw_documents import CorpusRawDocumentLink

if TYPE_CHECKING:
    from .raw_documents import RawDocument


class Corpus(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str | None = None
    raw_documents: list["RawDocument"] = Relationship(
        back_populates="corpora",
        link_model=CorpusRawDocumentLink,
    )
