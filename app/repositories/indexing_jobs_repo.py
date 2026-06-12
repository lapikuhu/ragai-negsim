from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.indexing_job_warnings import IndexingJobWarning
from app.models.indexing_jobs import IndexingJob
from app.repositories.helpers import commit_and_refresh, utc_now
from app.schemas.indexing_jobs_schemas import IndexingJobCreate


ACTIVE_INDEXING_JOB_STATUSES = {"queued", "running"}
TERMINAL_INDEXING_JOB_STATUSES = {"completed", "completed_with_warnings", "failed", "cancelled"}
_UNSET = object()


async def get_indexing_job_by_id(
    job_id: int,
    session: AsyncSession,
) -> IndexingJob | None:
    """
    Get an indexing job by its ID.
    Args:
        job_id: The ID of the indexing job to retrieve.
        session: The database session to use for the query.
    Returns:
        The indexing job if found, otherwise None.
    """
    return await session.get(IndexingJob, job_id)


async def get_active_indexing_job(session: AsyncSession) -> IndexingJob | None:
    """
    Get the currently active indexing job, if any.
    Args:
        session: The database session to use for the query.
    Returns:
        The active indexing job if found, otherwise None.
    """
    result = await session.exec(
        select(IndexingJob)
        .where(IndexingJob.status.in_(ACTIVE_INDEXING_JOB_STATUSES))
        .order_by(IndexingJob.id.desc())
    )
    return result.first()


async def create_indexing_job(
    job_in: IndexingJobCreate,
    session: AsyncSession,
) -> IndexingJob:
    """
    Create a new indexing job.
    Args:
        job_in: The indexing job data to create.
        session: The database session to use for the query.
    Returns:
        The created indexing job.
    Raises:
        ValueError: If another indexing job is already active.
    """
    if await get_active_indexing_job(session) is not None:
        raise ValueError("Another indexing job is already active")

    job = IndexingJob(**job_in.model_dump())
    return await commit_and_refresh(session, job)


async def list_indexing_jobs(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
    corpus_id: int | None = None,
) -> list[IndexingJob]:
    """
    List indexing jobs with optional filtering by status and corpus ID.
    Args:
        session: The database session to use for the query.
        skip: The number of records to skip for pagination.
        limit: The maximum number of records to return for pagination.
        status: Optional status to filter indexing jobs by.
        corpus_id: Optional corpus ID to filter indexing jobs by.
    Returns:
        A list of indexing jobs matching the specified criteria.
    """
    statement = select(IndexingJob)
    if status is not None:
        statement = statement.where(IndexingJob.status == status)
    if corpus_id is not None:
        statement = statement.where(IndexingJob.corpus_id == corpus_id)
    statement = statement.order_by(IndexingJob.id.desc()).offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def list_interrupted_indexing_jobs(
    session: AsyncSession,
) -> list[IndexingJob]:
    """
    List indexing jobs that were interrupted (i.e. have an active status 
    but were started a while ago).
    Args:
        session: The database session to use for the query.
    Returns:
        A list of interrupted indexing jobs.
    """
    result = await session.exec(
        select(IndexingJob)
        .where(IndexingJob.status.in_(ACTIVE_INDEXING_JOB_STATUSES))
        .order_by(IndexingJob.id.asc())
    )
    return list(result.all())


async def create_indexing_job_warning(
    *,
    indexing_job_id: int,
    stage: str,
    message: str,
    session: AsyncSession,
    raw_document_id: int | None = None,
    document_name: str | None = None,
) -> IndexingJobWarning:
    """
    Create a new indexing job warning.
    Args:
        indexing_job_id: The ID of the indexing job.
        stage: The stage of the indexing job.
        message: The warning message.
        session: The database session to use for the query.
        raw_document_id: Optional ID of the raw document associated with the warning.
        document_name: Optional name of the document associated with the warning.
    Returns:
        The created indexing job warning.
    """
    warning = IndexingJobWarning(
        indexing_job_id=indexing_job_id,
        raw_document_id=raw_document_id,
        document_name=document_name,
        stage=stage,
        message=message,
    )
    return await commit_and_refresh(session, warning)


async def list_indexing_job_warnings(
    indexing_job_id: int,
    session: AsyncSession,
) -> list[IndexingJobWarning]:
    """
    List warnings for a specific indexing job.
    Args:
        indexing_job_id: The ID of the indexing job.
        session: The database session to use for the query.
    Returns:
        A list of indexing job warnings.
    """
    result = await session.exec(
        select(IndexingJobWarning)
        .where(IndexingJobWarning.indexing_job_id == indexing_job_id)
        .order_by(IndexingJobWarning.id.asc())
    )
    return list(result.all())


async def update_indexing_job_progress(
    job: IndexingJob,
    session: AsyncSession,
    *,
    stage: str | None = None,
    current_raw_document_id: int | None | object = _UNSET,
    current_document_name: str | None | object = _UNSET,
    total_documents: int | None = None,
    processed_documents: int | None = None,
    chunks_created: int | None = None,
    chunks_indexed: int | None = None,
) -> IndexingJob:
    """
    Update the progress of an indexing job.
    Args:        
        job: The indexing job to update.
        session: The database session to use for the query.
        stage: Optional new stage of the indexing job.
        current_raw_document_id: Optional ID of the current raw document 
            being processed.
        current_document_name: Optional name of the current document being 
            processed.
        total_documents: Optional total number of documents to be processed.
        processed_documents: Optional number of documents processed so far.
        chunks_created: Optional number of chunks created so far.
        chunks_indexed: Optional number of chunks indexed so far.
    Returns:
        The updated indexing job.
    """
    if stage is not None:
        job.stage = stage
    if current_raw_document_id is not _UNSET:
        job.current_raw_document_id = current_raw_document_id
    if current_document_name is not _UNSET:
        job.current_document_name = current_document_name
    if total_documents is not None:
        job.total_documents = total_documents
    if processed_documents is not None:
        job.processed_documents = processed_documents
    if chunks_created is not None:
        job.chunks_created = chunks_created
    if chunks_indexed is not None:
        job.chunks_indexed = chunks_indexed
    return await commit_and_refresh(session, job)


async def request_indexing_job_cancel(
    job: IndexingJob,
    session: AsyncSession,
) -> IndexingJob:
    job.cancel_requested = True
    return await commit_and_refresh(session, job)


async def mark_indexing_job_running(
    job: IndexingJob,
    session: AsyncSession,
) -> IndexingJob:
    job.status = "running"
    job.cancel_requested = False
    job.started_at = utc_now()
    return await commit_and_refresh(session, job)


async def mark_indexing_job_completed(
    job: IndexingJob,
    session: AsyncSession,
    *,
    status: str,
    stage: str = "finished",
    completed_at: datetime | None = None,
    candidate_corpus_index_id: int | None = None,
    replaced_corpus_index_id: int | None = None,
) -> IndexingJob:
    """
    Mark an indexing job as completed.
    Args:
        job: The indexing job to update.
        session: The database session to use for the query.
        status: The new status of the indexing job.
        stage: The new stage of the indexing job.
        completed_at: The completion time of the indexing job.
        candidate_corpus_index_id: The ID of the candidate corpus index.
        replaced_corpus_index_id: The ID of the replaced corpus index.
    Returns:
        The updated indexing job.
    """
    job.status = status
    job.stage = stage
    job.cancel_requested = False
    job.completed_at = completed_at or utc_now()
    job.candidate_corpus_index_id = candidate_corpus_index_id
    job.replaced_corpus_index_id = replaced_corpus_index_id
    return await commit_and_refresh(session, job)


async def mark_indexing_job_failed(
    job: IndexingJob,
    failure_detail: str,
    session: AsyncSession,
) -> IndexingJob:
    """
    Mark an indexing job as failed.
    Args:
        job: The indexing job to update.
        failure_detail: The detail of the failure.
        session: The database session to use for the query.
    Returns:
        The updated indexing job.
    """
    job.status = "failed"
    job.stage = "finished"
    job.cancel_requested = False
    job.failure_detail = failure_detail
    job.completed_at = utc_now()
    return await commit_and_refresh(session, job)


async def mark_indexing_job_cancelled(
    job: IndexingJob,
    session: AsyncSession,
    *,
    detail: str | None = None,
) -> IndexingJob:
    job.status = "cancelled"
    job.stage = "finished"
    job.cancel_requested = True
    job.failure_detail = detail
    job.current_raw_document_id = None
    job.current_document_name = None
    job.completed_at = utc_now()
    return await commit_and_refresh(session, job)
