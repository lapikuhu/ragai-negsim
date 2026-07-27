from datetime import datetime, timezone
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import Column, DateTime as SQLAlchemyDateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .full_corpus_index_pipe_jobs import FullCorpusIndexPipeJob
    from .raw_documents import RawDocument

# Model for warnings that occur during full corpus index pipe jobs. 
# These are not critical errors, but they are important to track and 
# display to the user. 
# Note: too much abstraction at this point

class FullCorpusIndexPipeJobWarning(SQLModel, table=True):
    __tablename__: ClassVar[str] = "fullcorpusindexpipejobwarning"

    id: int | None = Field(default=None, primary_key=True)
    full_corpus_index_pipe_job_id: int = Field(foreign_key="fullcorpusindexpipejob.id", index=True)
    raw_document_id: int | None = Field(default=None, foreign_key="rawdocument.id")
    document_name: str | None = None
    stage: str = Field(min_length=1)
    message: str = Field(min_length=1)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )
    full_corpus_index_pipe_job: "FullCorpusIndexPipeJob" = Relationship(back_populates="warnings")
    raw_document: "RawDocument" = Relationship()
