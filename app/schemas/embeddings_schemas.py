from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel


class EmbeddingModelRead(SQLModel):
    name: str
    provider: str
    display_name: str
    dimensionality: int
    normalized: bool = False


class CorpusEmbeddingBuildRequest(SQLModel):
    name: str = Field(min_length=3, title="Corpus index name")
    embedding_model: str = Field(min_length=1, title="Embedding model")
    vector_namespace: str | None = None


class CorpusEmbeddingBuildQueued(SQLModel):
    corpus_id: int
    corpus_index_id: int
    vector_store_id: int
    chunking_profile_id: int
    embedding_model: str
    embedding_dimensions: int
    vector_namespace: str
    status: str = "building"
    poll_url: str | None = None
    indexed_chunks_url: str | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.poll_url is None:
            self.poll_url = f"/corpus-indices/{self.corpus_index_id}"
        if self.indexed_chunks_url is None:
            self.indexed_chunks_url = f"/corpus-indices/{self.corpus_index_id}/indexed-chunks"


class IndexedChunkBuildRef(SQLModel):
    document_chunk_id: int
    external_vector_id: str


class CorpusEmbeddingBuildResult(SQLModel):
    corpus_id: int
    corpus_index_id: int
    vector_store_id: int
    chunking_profile_id: int
    embedding_model: str
    embedding_dimensions: int
    vector_namespace: str
    status: str
    built_at: datetime | None = None
    chunks_indexed: int = 0
    indexed_chunks: list[IndexedChunkBuildRef] = Field(default_factory=list)
    store_metadata: dict[str, Any] = Field(default_factory=dict)
