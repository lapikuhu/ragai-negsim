from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.full_corpus_index_pipe_job_warnings import FullCorpusIndexPipeJobWarning
from app.models.full_corpus_index_pipe_jobs import FullCorpusIndexPipeJob
from app.repositories.helpers import commit_and_refresh, utc_now
from app.schemas.full_corpus_index_pipe_jobs_schemas import FullCorpusIndexPipeJobPersist


ACTIVE_FULL_CORPUS_INDEX_PIPE_JOB_STATUSES = {"queued", "running"}
TERMINAL_FULL_CORPUS_INDEX_PIPE_JOB_STATUSES = {"completed", "completed_with_warnings", "failed", "cancelled"}
_UNSET = object()


async def get_full_corpus_index_pipe_job_by_id(
    job_id: int,
    session: AsyncSession,
) -> FullCorpusIndexPipeJob | None:
    """
    Get an full corpus index pipe job by its ID.
    Args:
        job_id: The ID of the full corpus index pipe job to retrieve.
        session: The database session to use for the query.
    Returns:
        The full corpus index pipe job if found, otherwise None.
    """
    return await session.get(FullCorpusIndexPipeJob, job_id)


async def get_active_full_corpus_index_pipe_job(session: AsyncSession) -> FullCorpusIndexPipeJob | None:
    """
    Get the currently active full corpus index pipe job, if any.
    Args:
        session: The database session to use for the query.
    Returns:
        The active full corpus index pipe job if found, otherwise None.
    """
    result = await session.exec(
        select(FullCorpusIndexPipeJob)
        .where(FullCorpusIndexPipeJob.status.in_(ACTIVE_FULL_CORPUS_INDEX_PIPE_JOB_STATUSES))
        .order_by(FullCorpusIndexPipeJob.id.desc())
    )
    return result.first()


async def claim_next_full_corpus_index_pipe_job(
    session: AsyncSession,
) -> FullCorpusIndexPipeJob | None:
    """
    Claim rollback work first, otherwise the oldest queued parent.

    Args:
        session: The database session to use for the query.
    Returns:
        The claimed full corpus index pipe job if available, otherwise None.
    """
    rollback_result = await session.exec(
        select(FullCorpusIndexPipeJob)
        .where(
            FullCorpusIndexPipeJob.status == "running",
            FullCorpusIndexPipeJob.stage == "rolling_back",
        )
        .order_by(FullCorpusIndexPipeJob.queued_at, FullCorpusIndexPipeJob.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    rollback_job = rollback_result.first()
    if rollback_job is not None:
        return rollback_job

    queued_result = await session.exec(
        select(FullCorpusIndexPipeJob)
        .where(FullCorpusIndexPipeJob.status == "queued")
        .order_by(FullCorpusIndexPipeJob.queued_at, FullCorpusIndexPipeJob.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = queued_result.first()
    if job is None:
        return None
    job.status = "running"
    job.started_at = utc_now()
    job.cancel_requested = False
    return await commit_and_refresh(session, job)


async def create_full_corpus_index_pipe_job(
    job_in: FullCorpusIndexPipeJobPersist,
    session: AsyncSession,
) -> FullCorpusIndexPipeJob:
    """
    Create a new full corpus index pipe job.
    Args:
        job_in: The full corpus index pipe job data to create.
        session: The database session to use for the query.
    Returns:
        The created full corpus index pipe job.
    Raises:
        ValueError: If another full corpus index pipe job is already active.
    """
    if await get_active_full_corpus_index_pipe_job(session) is not None:
        raise ValueError("Another full corpus index pipe job is already active")

    job = FullCorpusIndexPipeJob(**job_in.model_dump())
    return await commit_and_refresh(session, job)


async def set_full_corpus_index_pipe_job_bm25_child(
    job: FullCorpusIndexPipeJob,
    bm25_build_job_id: int,
    session: AsyncSession,
) -> FullCorpusIndexPipeJob:
    """
    Link a queued BM25 child and expose that the parent is waiting on it.

    Args:
        job: The full corpus index pipe job instance to update.
        bm25_build_job_id: The ID of the BM25 build job to link.
        session: The database session.
    Returns:
        The updated full corpus index pipe job.
    """
    job.bm25_build_job_id = bm25_build_job_id
    job.stage = "building_bm25"
    return await commit_and_refresh(session, job)


async def set_full_corpus_index_pipe_job_chunk_set(
    job: FullCorpusIndexPipeJob,
    chunk_set_id: int,
    session: AsyncSession,
) -> FullCorpusIndexPipeJob:
    """
    Link a queued chunk set and expose that the parent is waiting on it.

    Args:
        job: The full corpus index pipe job instance to update.
        chunk_set_id: The ID of the chunk set to link.
        session: The database session.
    Returns:
        The updated full corpus index pipe job.
    """
    job.corpus_chunk_set_id = chunk_set_id
    return await commit_and_refresh(session, job)


async def has_active_full_pipe_bm25_name_reservation(
    requested_name: str,
    session: AsyncSession,
) -> bool:
    """
    Check if there is an active full pipe BM25 name reservation.

    Args:
        requested_name: The requested BM25 index name to check for.
        session: The database session.
    Returns:
        True if there is an active reservation with the requested name, False otherwise.
    """
    result = await session.exec(
        select(FullCorpusIndexPipeJob.id)
        .where(
            FullCorpusIndexPipeJob.build_bm25.is_(True),
            FullCorpusIndexPipeJob.requested_bm25_index_name == requested_name,
            FullCorpusIndexPipeJob.status.in_(ACTIVE_FULL_CORPUS_INDEX_PIPE_JOB_STATUSES),
        )
        .limit(1)
    )
    return result.first() is not None


async def has_active_full_pipe_chunk_set_name_reservation(
    corpus_id: int,
    requested_name: str,
    session: AsyncSession,
) -> bool:
    """
    Check if there is an active full pipe chunk set name reservation.

    Args:
        corpus_id: The ID of the corpus to check for.
        requested_name: The requested chunk set name to check for.
        session: The database session.
    Returns:
        True if there is an active reservation with the requested name, False otherwise.
    """
    result = await session.exec(
        select(FullCorpusIndexPipeJob.id)
        .where(
            FullCorpusIndexPipeJob.corpus_id == corpus_id,
            FullCorpusIndexPipeJob.requested_chunk_set_name == requested_name,
            FullCorpusIndexPipeJob.status.in_(ACTIVE_FULL_CORPUS_INDEX_PIPE_JOB_STATUSES),
        )
        .limit(1)
    )
    return result.first() is not None


async def list_full_corpus_index_pipe_jobs(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
    corpus_id: int | None = None,
) -> list[FullCorpusIndexPipeJob]:
    """
    List full corpus index pipe jobs with optional filtering by status and corpus ID.
    Args:
        session: The database session to use for the query.
        skip: The number of records to skip for pagination.
        limit: The maximum number of records to return for pagination.
        status: Optional status to filter full corpus index pipe jobs by.
        corpus_id: Optional corpus ID to filter full corpus index pipe jobs by.
    Returns:
        A list of full corpus index pipe jobs matching the specified criteria.
    """
    statement = select(FullCorpusIndexPipeJob)
    if status is not None:
        statement = statement.where(FullCorpusIndexPipeJob.status == status)
    if corpus_id is not None:
        statement = statement.where(FullCorpusIndexPipeJob.corpus_id == corpus_id)
    statement = statement.order_by(FullCorpusIndexPipeJob.id.desc()).offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def list_interrupted_full_corpus_index_pipe_jobs(
    session: AsyncSession,
) -> list[FullCorpusIndexPipeJob]:
    """
    List full corpus index pipe jobs that were interrupted (i.e. have an active status 
    but were started a while ago).
    Args:
        session: The database session to use for the query.
    Returns:
        A list of interrupted full corpus index pipe jobs.
    """
    result = await session.exec(
        select(FullCorpusIndexPipeJob)
        .where(FullCorpusIndexPipeJob.status.in_(ACTIVE_FULL_CORPUS_INDEX_PIPE_JOB_STATUSES))
        .order_by(FullCorpusIndexPipeJob.id.asc())
    )
    return list(result.all())


async def create_full_corpus_index_pipe_job_warning(
    *,
    full_corpus_index_pipe_job_id: int,
    stage: str,
    message: str,
    session: AsyncSession,
    raw_document_id: int | None = None,
    document_name: str | None = None,
) -> FullCorpusIndexPipeJobWarning:
    """
    Create a new full corpus index pipe job warning.
    Args:
        full_corpus_index_pipe_job_id: The ID of the full corpus index pipe job.
        stage: The stage of the full corpus index pipe job.
        message: The warning message.
        session: The database session to use for the query.
        raw_document_id: Optional ID of the raw document associated with the warning.
        document_name: Optional name of the document associated with the warning.
    Returns:
        The created full corpus index pipe job warning.
    """
    warning = FullCorpusIndexPipeJobWarning(
        full_corpus_index_pipe_job_id=full_corpus_index_pipe_job_id,
        raw_document_id=raw_document_id,
        document_name=document_name,
        stage=stage,
        message=message,
    )
    return await commit_and_refresh(session, warning)


async def list_full_corpus_index_pipe_job_warnings(
    full_corpus_index_pipe_job_id: int,
    session: AsyncSession,
) -> list[FullCorpusIndexPipeJobWarning]:
    """
    List warnings for a specific full corpus index pipe job.
    Args:
        full_corpus_index_pipe_job_id: The ID of the full corpus index pipe job.
        session: The database session to use for the query.
    Returns:
        A list of full corpus index pipe job warnings.
    """
    result = await session.exec(
        select(FullCorpusIndexPipeJobWarning)
        .where(FullCorpusIndexPipeJobWarning.full_corpus_index_pipe_job_id == full_corpus_index_pipe_job_id)
        .order_by(FullCorpusIndexPipeJobWarning.id.asc())
    )
    return list(result.all())


async def update_full_corpus_index_pipe_job_progress(
    job: FullCorpusIndexPipeJob,
    session: AsyncSession,
    *,
    stage: str | None = None,
    current_raw_document_id: int | None | object = _UNSET,
    current_document_name: str | None | object = _UNSET,
    total_documents: int | None = None,
    processed_documents: int | None = None,
    chunks_created: int | None = None,
    chunks_indexed: int | None = None,
) -> FullCorpusIndexPipeJob:
    """
    Update the progress of an full corpus index pipe job.
    Args:        
        job: The full corpus index pipe job to update.
        session: The database session to use for the query.
        stage: Optional new stage of the full corpus index pipe job.
        current_raw_document_id: Optional ID of the current raw document 
            being processed.
        current_document_name: Optional name of the current document being 
            processed.
        total_documents: Optional total number of documents to be processed.
        processed_documents: Optional number of documents processed so far.
        chunks_created: Optional number of chunks created so far.
        chunks_indexed: Optional number of chunks indexed so far.
    Returns:
        The updated full corpus index pipe job.
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


async def mark_full_corpus_index_pipe_job_rolling_back(
    job: FullCorpusIndexPipeJob,
    failure_detail: str,
    session: AsyncSession,
) -> FullCorpusIndexPipeJob:
    """
    Keep a parent non-terminal until its artifact rollback succeeds.

    Args:
        job: The full corpus index pipe job to update.
        failure_detail: The failure detail message for the rollback.
        session: The database session to use for the query.
    Returns:
        The updated full corpus index pipe job.
    """
    job.status = "running"
    job.stage = "rolling_back"
    job.failure_detail = failure_detail
    return await commit_and_refresh(session, job)


async def request_full_corpus_index_pipe_job_cancel(
    job: FullCorpusIndexPipeJob,
    session: AsyncSession,
) -> FullCorpusIndexPipeJob:
    """
    Request cancellation of an full corpus index pipe job.
    Args:
        job: The full corpus index pipe job to cancel.
        session: The database session to use for the query.
    Returns:
        The updated full corpus index pipe job with cancellation requested.
    """
    job.cancel_requested = True
    return await commit_and_refresh(session, job)


async def mark_full_corpus_index_pipe_job_running(
    job: FullCorpusIndexPipeJob,
    session: AsyncSession,
) -> FullCorpusIndexPipeJob:
    """
    Mark an full corpus index pipe job as running.
    Args:
        job: The full corpus index pipe job to update.
        session: The database session to use for the query.
    Returns:
        The updated full corpus index pipe job.
    """
    job.status = "running"
    job.cancel_requested = False
    job.started_at = utc_now()
    return await commit_and_refresh(session, job)


async def mark_full_corpus_index_pipe_job_completed(
    job: FullCorpusIndexPipeJob,
    session: AsyncSession,
    *,
    status: str,
    stage: str = "finished",
    completed_at: datetime | None = None,
    candidate_corpus_index_id: int | None = None,
    replaced_corpus_index_id: int | None = None,
) -> FullCorpusIndexPipeJob:
    """
    Mark an full corpus index pipe job as completed.
    Args:
        job: The full corpus index pipe job to update.
        session: The database session to use for the query.
        status: The new status of the full corpus index pipe job.
        stage: The new stage of the full corpus index pipe job.
        completed_at: The completion time of the full corpus index pipe job.
        candidate_corpus_index_id: The ID of the candidate corpus index.
        replaced_corpus_index_id: The ID of the replaced corpus index.
    Returns:
        The updated full corpus index pipe job.
    """
    job.status = status
    job.stage = stage
    job.cancel_requested = False
    job.completed_at = completed_at or utc_now()
    job.candidate_corpus_index_id = candidate_corpus_index_id
    job.replaced_corpus_index_id = replaced_corpus_index_id
    return await commit_and_refresh(session, job)


async def mark_full_corpus_index_pipe_job_failed(
    job: FullCorpusIndexPipeJob,
    failure_detail: str,
    session: AsyncSession,
) -> FullCorpusIndexPipeJob:
    """
    Mark an full corpus index pipe job as failed.
    Args:
        job: The full corpus index pipe job to update.
        failure_detail: The detail of the failure.
        session: The database session to use for the query.
    Returns:
        The updated full corpus index pipe job.
    """
    job.status = "failed"
    job.stage = "finished"
    job.cancel_requested = False
    job.failure_detail = failure_detail
    job.completed_at = utc_now()
    return await commit_and_refresh(session, job)


async def mark_full_corpus_index_pipe_job_cancelled(
    job: FullCorpusIndexPipeJob,
    session: AsyncSession,
    *,
    detail: str | None = None,
) -> FullCorpusIndexPipeJob:
    """
    Mark an full corpus index pipe job as cancelled.
    Args:
        job: The full corpus index pipe job to update.
        session: The database session to use for the query.
        detail: The detail of the cancellation.
    Returns:
        The updated full corpus index pipe job.
    """
    job.status = "cancelled"
    job.stage = "finished"
    job.cancel_requested = True
    job.failure_detail = detail
    job.current_raw_document_id = None
    job.current_document_name = None
    job.completed_at = utc_now()
    return await commit_and_refresh(session, job)
