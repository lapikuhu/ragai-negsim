from sqlmodel import Field, SQLModel


class RawDocumentIngestResult(SQLModel):
    raw_document_id: int
    chunking_profile_id: int
    chunks_created: int
    chunk_ids: list[int] = Field(default_factory=list)


class CorpusIngestResult(SQLModel):
    corpus_id: int
    chunking_profile_id: int
    raw_documents: list[RawDocumentIngestResult] = Field(default_factory=list)
    chunks_created: int
