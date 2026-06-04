from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .chunking_profiles import ChunkingProfile
    from .corpus import Corpus
    from .indexed_chunks import IndexedChunk
    from .simulations import Simulation
    from .vector_stores import VectorStore


class CorpusIndex(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    corpus_id: int = Field(foreign_key="corpus.id")
    vector_store_id: int = Field(foreign_key="vectorstore.id")
    chunking_profile_id: int = Field(foreign_key="chunkingprofile.id")
    name: str = Field(index=True, unique=True, min_length=3, title="Corpus index name")
    status: str = Field(default="created", index=True, min_length=1, title="Corpus index status")
    embedding_model: str = Field(min_length=1, title="Embedding model")
    embedding_dimensions: int | None = Field(default=None, ge=1)
    vector_namespace: str | None = None
    built_at: datetime | None = None
    corpus: "Corpus" = Relationship(back_populates="corpus_indices")
    vector_store: "VectorStore" = Relationship(back_populates="corpus_indices")
    chunking_profile: "ChunkingProfile" = Relationship(back_populates="corpus_indices")
    indexed_chunks: list["IndexedChunk"] = Relationship(back_populates="corpus_index")
    simulations: list["Simulation"] = Relationship(back_populates="corpus_index")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
