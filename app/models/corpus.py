from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel

from .raw_documents import CorpusRawDocumentLink

if TYPE_CHECKING:
    from .corpus_indices import CorpusIndex
    from .raw_documents import RawDocument
    from .users import User
    from .simulations import Simulation


class Corpus(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str | None = None
    created_by_user_id: int = Field(foreign_key="user.id")
    created_by_user: "User" = Relationship(
        back_populates="corpora_created",
        sa_relationship_kwargs={"foreign_keys": "[Corpus.created_by_user_id]"},
    )
    last_edit_by_user_id: int | None = Field(default=None, foreign_key="user.id")
    last_edit_by_user: Optional["User"] = Relationship(
        back_populates="corpora_last_edited",
        sa_relationship_kwargs={"foreign_keys": "[Corpus.last_edit_by_user_id]"},
    )
    raw_documents: list["RawDocument"] = Relationship(
        back_populates="corpora",
        link_model=CorpusRawDocumentLink,
    )
    corpus_indices: list["CorpusIndex"] = Relationship(back_populates="corpus")
    simulations: list["Simulation"] = Relationship(back_populates="corpus")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

