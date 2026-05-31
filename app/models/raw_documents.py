from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .corpus import Corpus


class CorpusRawDocumentLink(SQLModel, table=True):
    corpus_id: int | None = Field(default=None, foreign_key="corpus.id", primary_key=True)
    raw_document_id: int | None = Field(default=None, foreign_key="rawdocument.id", primary_key=True)


class RawDocument(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)         # e.g. "employee_handbook"
    description: str | None = None
    path: str = Field(index=True, unique=True)         # e.g. "s3://bucket/employee_handbook.pdf"
    corpora: list["Corpus"] = Relationship(
        back_populates="raw_documents",
        link_model=CorpusRawDocumentLink,
    )