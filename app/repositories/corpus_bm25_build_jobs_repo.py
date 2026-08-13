from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.corpus_bm25_build_jobs import CorpusBm25BuildJob
from app.repositories.helpers import commit_and_refresh, utc_now
from app.schemas.corpus_bm25_build_jobs_schemas import CorpusBm25BuildJobCreate


ACTIVE_CORPUS_BM25_BUILD_JOB_STATUSES = {"queued", "running"}
TERMINAL_CORPUS_BM25_BUILD_JOB_STATUSES = {"completed", "failed", "cancelled"}
CORPUS_BM25_BUILD_JOB_STAGES = {
    "queued",
    "validating_snapshot",
    "building_artifact",
    "persisting_artifact",
    "finished",
}


async def create_corpus_bm25_build_job(
    job_in: CorpusBm25BuildJobCreate,
    session: AsyncSession,
) -> CorpusBm25BuildJob:
    """
    Create a new CorpusBm25BuildJob in the database.
    Args:
        job_in: The CorpusBm25BuildJobCreate schema instance.
        session: The database session.
    Returns:
        The created CorpusBm25BuildJob instance.
    """
    return await commit_and_refresh(session, CorpusBm25BuildJob(**job_in.model_dump()))


async def get_corpus_bm25_build_job_by_id(
    job_id: int, session: AsyncSession
) -> CorpusBm25BuildJob | None:
    """
    Get a CorpusBm25BuildJob by its ID.

    Args:
        job_id: The ID of the CorpusBm25BuildJob.
        session: The database session.
    Returns:
        The CorpusBm25BuildJob instance if found, else None.    
    """
    return await session.get(CorpusBm25BuildJob, job_id)


async def list_corpus_bm25_build_jobs(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 20,
    corpus_id: int | None = None,
    status: str | None = None,
) -> list[CorpusBm25BuildJob]:
    """
    List CorpusBm25BuildJobs with optional filters.

    Args:
        session: The database session.
        skip: The number of records to skip for pagination.
        limit: The maximum number of records to return.
        corpus_id: Optional filter by corpus ID.
        status: Optional filter by job status.
    Returns:
        A list of CorpusBm25BuildJob instances matching the filters.
    """
    statement = select(CorpusBm25BuildJob)
    if corpus_id is not None:
        statement = statement.where(CorpusBm25BuildJob.corpus_id == corpus_id)
    if status is not None:
        statement = statement.where(CorpusBm25BuildJob.status == status)
    result = await session.exec(
        statement.order_by(CorpusBm25BuildJob.queued_at.desc(), CorpusBm25BuildJob.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.all())


async def claim_next_corpus_bm25_build_job(
    session: AsyncSession,
) -> CorpusBm25BuildJob | None:
    """
    Claim the next queued CorpusBm25BuildJob for processing.
    
    Args:
        session: The database session.
    Returns:
        The claimed CorpusBm25BuildJob instance if available, else None.
    """
    
    result = await session.exec(
        select(CorpusBm25BuildJob)
        .where(CorpusBm25BuildJob.status == "queued")
        .order_by(CorpusBm25BuildJob.queued_at, CorpusBm25BuildJob.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = result.first()
    if job is None:
        return None
    job.status = "running"
    job.stage = "validating_snapshot"
    job.started_at = utc_now()
    job.cancel_requested = False
    return await commit_and_refresh(session, job)


async def list_interrupted_corpus_bm25_build_jobs(
    session: AsyncSession,
) -> list[CorpusBm25BuildJob]:
    """
    Get and list all CorpusBm25BuildJobs that are currently marked as 
    "running".

    Args:
        session: The database session.
    Returns:
        A list of CorpusBm25BuildJob instances that are currently running.
    """
    result = await session.exec(
        select(CorpusBm25BuildJob)
        .where(CorpusBm25BuildJob.status == "running")
        .order_by(CorpusBm25BuildJob.id)
    )
    return list(result.all())


async def request_corpus_bm25_build_job_cancel(
    job: CorpusBm25BuildJob,
    session: AsyncSession,
) -> CorpusBm25BuildJob:
    """
    Request cancellation of a CorpusBm25BuildJob.

    Args:
        job: The CorpusBm25BuildJob instance to cancel.
        session: The database session.
    Returns:
        The updated CorpusBm25BuildJob instance.
    """
    if job.status in TERMINAL_CORPUS_BM25_BUILD_JOB_STATUSES:
        raise ValueError("BM25 build job is already terminal")
    job.cancel_requested = True
    if job.status == "queued":
        job.status = "cancelled"
        job.stage = "finished"
        job.completed_at = utc_now()
    return await commit_and_refresh(session, job)


async def mark_corpus_bm25_build_job_stage(
    job: CorpusBm25BuildJob,
    stage: str,
    session: AsyncSession,
    *,
    result_bm25_index_id: int | None = None,
) -> CorpusBm25BuildJob:
    """
    Mark the stage of a CorpusBm25BuildJob.

    Args:
        job: The CorpusBm25BuildJob instance to update.
        stage: The new stage to set.
        session: The database session.
        result_bm25_index_id: Optional ID of the resulting BM25 index.
    Returns:
        The updated CorpusBm25BuildJob instance.
    """
    if stage not in CORPUS_BM25_BUILD_JOB_STAGES:
        raise ValueError("Invalid BM25 build job stage")
    job.stage = stage
    if result_bm25_index_id is not None:
        job.result_bm25_index_id = result_bm25_index_id
    return await commit_and_refresh(session, job)


async def mark_corpus_bm25_build_job_completed(
    job: CorpusBm25BuildJob,
    result_bm25_index_id: int,
    session: AsyncSession,
) -> CorpusBm25BuildJob:
    """
    Mark a CorpusBm25BuildJob as completed.

    Args:
        job: The CorpusBm25BuildJob instance to update.
        result_bm25_index_id: ID of the resulting BM25 index.
        session: The database session.
    Returns:
        The updated CorpusBm25BuildJob instance.
    """
    job.status = "completed"
    job.stage = "finished"
    job.cancel_requested = False
    job.result_bm25_index_id = result_bm25_index_id
    job.failure_detail = None
    job.completed_at = utc_now()
    return await commit_and_refresh(session, job)


async def mark_corpus_bm25_build_job_failed(
    job: CorpusBm25BuildJob,
    failure_detail: str,
    session: AsyncSession,
) -> CorpusBm25BuildJob:
    """
    Mark a CorpusBm25BuildJob as failed.

    Args:
        job: The CorpusBm25BuildJob instance to update.
        failure_detail: Details of the failure.
        session: The database session.
    Returns:
        The updated CorpusBm25BuildJob instance.
    """
    job.status = "failed"
    job.stage = "finished"
    job.cancel_requested = False
    job.failure_detail = failure_detail
    job.completed_at = utc_now()
    return await commit_and_refresh(session, job)


async def mark_corpus_bm25_build_job_cancelled(
    job: CorpusBm25BuildJob,
    session: AsyncSession,
    detail: str | None = None,
) -> CorpusBm25BuildJob:
    """
    Mark a CorpusBm25BuildJob as cancelled.

    Args:
        job: The CorpusBm25BuildJob instance to update.
        session: The database session.
        detail: Optional details about the cancellation.
    Returns:
        The updated CorpusBm25BuildJob instance.
    """
    job.status = "cancelled"
    job.stage = "finished"
    job.cancel_requested = True
    job.failure_detail = detail
    job.completed_at = utc_now()
    return await commit_and_refresh(session, job)
