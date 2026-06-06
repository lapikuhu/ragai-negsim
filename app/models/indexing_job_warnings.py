from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime as SQLAlchemyDateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .indexing_jobs import IndexingJob
    from .raw_documents import RawDocument

# Model for warnings that occur during indexing jobs. 
# These are not critical errors, but they are important to track and 
# display to the user. 
# Note: too much abstraction at this point

class IndexingJobWarning(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    indexing_job_id: int = Field(foreign_key="indexingjob.id", index=True)
    raw_document_id: int | None = Field(default=None, foreign_key="rawdocument.id")
    document_name: str | None = None
    stage: str = Field(min_length=1)
    message: str = Field(min_length=1)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(SQLAlchemyDateTime(timezone=True), nullable=False),
    )
    indexing_job: "IndexingJob" = Relationship(back_populates="warnings")
    raw_document: "RawDocument" = Relationship()
