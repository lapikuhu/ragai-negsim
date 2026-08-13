import asyncio
from datetime import datetime, timezone

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.users import User
from app.repositories import (
    chunking_profiles_repo,
    corpus_bm25_build_jobs_repo, #as repository,
    corpus_bm25_indices_repo,
    corpus_repo,
    document_chunks_repo,
)
from app.schemas.corpus_bm25_build_jobs_schemas import (
    CorpusBm25BuildJobCreate,
    CorpusBm25BuildJobQueueRequest,
    CorpusBm25BuildJobRead,
    CorpusBm25BuildJobRetryRequest,
)
from app.services.corpus_bm25_indices_service import build_corpus_bm25_index_from_snapshot_srvc
from app.services.helpers import _persisted_id


class CorpusBm25BuildJobNotFoundError(ValueError):
    pass


class CorpusBm25BuildJobConflictError(ValueError):
    pass


def _read(job) -> CorpusBm25BuildJobRead:
    """
    Convert a job model instance to a CorpusBm25BuildJobRead schema instance.

    Args:
        job: The job model instance to convert.

    Returns:
        CorpusBm25BuildJobRead: The corresponding schema instance.
    """
    return CorpusBm25BuildJobRead.model_validate(job)


async def _ensure_resources(corpus_id: int, 
                            profile_id: int, 
                            session: AsyncSession) -> None:
    """
    Ensure that the required resources exist.

    Args:
        corpus_id: The ID of the corpus.
        profile_id: The ID of the chunking profile.
        session: The database session.

    Raises:
        CorpusBm25BuildJobNotFoundError: If the corpus or chunking profile 
        is not found.
    """
    if await corpus_repo.get_corpus_by_id(corpus_id, session) is None:
        raise CorpusBm25BuildJobNotFoundError("Corpus not found")
    if await chunking_profiles_repo.get_chunking_profile_by_id(profile_id, session) is None:
        raise CorpusBm25BuildJobNotFoundError("Chunking profile not found")


async def queue_corpus_bm25_build_job_srvc(request: CorpusBm25BuildJobQueueRequest,
                                           current_user: User,
                                           session: AsyncSession,
) -> CorpusBm25BuildJobRead:
    """
    Queue a new BM25 build job for a given corpus and chunking profile.

    Args:
        request: The CorpusBm25BuildJobQueueRequest containing the job details.
        current_user: The user requesting the job.
        session: The database session.
    Returns:
        CorpusBm25BuildJobRead: The created BM25 build job.
    Raises:
        CorpusBm25BuildJobNotFoundError: If the corpus or chunking profile 
            is not found.
        CorpusBm25BuildJobConflictError: If there are no persisted chunks 
            available for the corpus and chunking profile.
    """
    await _ensure_resources(request.corpus_id, request.chunking_profile_id, session)
    chunks = await document_chunks_repo.list_corpus_document_chunks_for_profile(
        request.corpus_id, request.chunking_profile_id, session
    )
    if not chunks:
        raise CorpusBm25BuildJobConflictError(
            "No persisted chunks are available for this corpus and chunking profile"
        )
    chunk_ids = sorted(_persisted_id(chunk.id, "Document chunk") for chunk in chunks)
    # Create the BM25 build job
    job = await corpus_bm25_build_jobs_repo.create_corpus_bm25_build_job(
        CorpusBm25BuildJobCreate(
            requested_artifact_name=request.requested_artifact_name.strip(),
            corpus_id=request.corpus_id,
            chunking_profile_id=request.chunking_profile_id,
            requested_by_user_id=_persisted_id(current_user.id, "User"),
            document_chunk_ids=chunk_ids,
            document_chunk_ids_checksum=corpus_bm25_indices_repo.document_chunk_ids_checksum(chunk_ids),
            distinct_document_count=len({chunk.raw_document_id for chunk in chunks}),
            chunk_count=len(chunk_ids),
        ),
        session,
    )
    return _read(job)


async def list_corpus_bm25_build_jobs_srvc(*, 
                                           session: AsyncSession, 
                                           skip: int, limit: int, 
                                           corpus_id: int | None, 
                                           status: str | None
) -> list[CorpusBm25BuildJobRead]:
    """
    List BM25 build jobs with optional filtering by corpus ID and status.

    Args:
        session: The database session.
        skip: The number of jobs to skip.
        limit: The maximum number of jobs to return.
        corpus_id: Optional corpus ID to filter jobs.
        status: Optional status to filter jobs.
    Returns:
        list[CorpusBm25BuildJobRead]: The list of BM25 build jobs.
    """
    jobs = await corpus_bm25_build_jobs_repo.list_corpus_bm25_build_jobs(
        session, skip=skip, limit=limit, corpus_id=corpus_id, status=status
    )
    return [_read(job) for job in jobs]


async def get_corpus_bm25_build_job_srvc(job_id: int, 
                                         session: AsyncSession) -> CorpusBm25BuildJobRead:
    """
    Get a BM25 build job by its ID.

    Args:
        job_id: The ID of the BM25 build job.
        session: The database session.
    Returns:
        CorpusBm25BuildJobRead: The BM25 build job.
    Raises:
        CorpusBm25BuildJobNotFoundError: If the job is not found.
    """
    job = await corpus_bm25_build_jobs_repo.get_corpus_bm25_build_job_by_id(job_id, session)
    if job is None:
        raise CorpusBm25BuildJobNotFoundError("BM25 build job not found")
    return _read(job)


async def cancel_corpus_bm25_build_job_srvc(job_id: int, 
                                            session: AsyncSession) -> CorpusBm25BuildJobRead:
    """
    Cancel a BM25 build job by its ID.

    Args:
        job_id: The ID of the BM25 build job.
        session: The database session.
    Returns:
        CorpusBm25BuildJobRead: The BM25 build job.
    Raises:
        CorpusBm25BuildJobNotFoundError: If the job is not found.
        CorpusBm25BuildJobConflictError: If the job cannot be cancelled.
    """
    job = await corpus_bm25_build_jobs_repo.get_corpus_bm25_build_job_by_id(job_id, session)
    if job is None:
        raise CorpusBm25BuildJobNotFoundError("BM25 build job not found")
    try:
        return _read(await corpus_bm25_build_jobs_repo.request_corpus_bm25_build_job_cancel(job, session))
    except ValueError as exc:
        raise CorpusBm25BuildJobConflictError(str(exc)) from exc


async def retry_corpus_bm25_build_job_srvc(
    job_id: int,
    request: CorpusBm25BuildJobRetryRequest,
    current_user: User,
    session: AsyncSession,
) -> CorpusBm25BuildJobRead:
    """
    Retry a failed or cancelled BM25 build job by creating a new job with the 
    same parameters.

    Args:
        job_id: The ID of the BM25 build job to retry.
        request: The retry request containing the requested artifact name.
        current_user: The user requesting the retry.
        session: The database session.
    Returns:
        CorpusBm25BuildJobRead: The new BM25 build job.
    Raises:
        CorpusBm25BuildJobNotFoundError: If the original job is not found.
        CorpusBm25BuildJobConflictError: If the job cannot be retried.
    """
    old = await corpus_bm25_build_jobs_repo.get_corpus_bm25_build_job_by_id(job_id, session)
    if old is None:
        raise CorpusBm25BuildJobNotFoundError("BM25 build job not found")
    if old.status not in {"failed", "cancelled"}:
        raise CorpusBm25BuildJobConflictError("Only failed or cancelled BM25 jobs can be retried")
    name = request.requested_artifact_name or (
        f"{old.requested_artifact_name} retry {datetime.now(timezone.utc):%Y%m%d%H%M%S}"
    )
    return await queue_corpus_bm25_build_job_srvc(
        CorpusBm25BuildJobQueueRequest(
            requested_artifact_name=name,
            corpus_id=old.corpus_id,
            chunking_profile_id=old.chunking_profile_id,
        ), current_user, session
    )


async def execute_corpus_bm25_build_job_srvc(job_id: int, 
                                             session: AsyncSession) -> CorpusBm25BuildJobRead:
    """
    Execute a BM25 build job by its ID. This function will handle the entire
    lifecycle of the job, including checking for cancellation requests and
    updating the job status accordingly.

    Args:
        job_id: The ID of the BM25 build job to execute.
        session: The database session.
    Returns:
        CorpusBm25BuildJobRead: The updated BM25 build job after execution.
    Raises:
        CorpusBm25BuildJobNotFoundError: If the job is not found.
    """
    # Get the job
    job = await corpus_bm25_build_jobs_repo.get_corpus_bm25_build_job_by_id(job_id, session)
    if job is None:
        raise CorpusBm25BuildJobNotFoundError("BM25 build job not found")
    # Check that the job has not been cancelled before starting
    if job.cancel_requested:
        return _read(await corpus_bm25_build_jobs_repo.mark_corpus_bm25_build_job_cancelled(job, session))
    # Get the current set of persisted document chunks for the corpus and chunking profile
    chunks = await document_chunks_repo.list_corpus_document_chunks_for_profile(
        job.corpus_id, job.chunking_profile_id, session
    )
    current_ids = sorted(_persisted_id(chunk.id, "Document chunk") for chunk in chunks)
    if current_ids != job.document_chunk_ids:
        return _read(await corpus_bm25_build_jobs_repo.mark_corpus_bm25_build_job_failed(
            job,
            "The corpus chunk set changed since the job was queued. Retry to build the current snapshot.",
            session,
        ))

    async def link_index(index_id: int) -> None:
        """
        Link the BM25 index to the build job.

        Args:
            index_id: The ID of the newly created BM25 index.

        Returns:
            None
        """
        await corpus_bm25_build_jobs_repo.mark_corpus_bm25_build_job_stage(
            job, "building_artifact", session, result_bm25_index_id=index_id
        )

    async def stop_if_cancelled() -> None:
        """
        Check if the BM25 build job has been cancelled. Stops with an 
        asyncio.CancelledError if cancellation is requested.

        Raises:
            asyncio.CancelledError: If the job has been cancelled.
        """
        refreshed = await corpus_bm25_build_jobs_repo.get_corpus_bm25_build_job_by_id(job_id, session)
        if refreshed is not None and refreshed.cancel_requested:
            raise asyncio.CancelledError("BM25 build cancellation requested")

    try:
        metadata = await build_corpus_bm25_index_from_snapshot_srvc(
            name=job.requested_artifact_name,
            corpus_id=job.corpus_id,
            chunking_profile_id=job.chunking_profile_id,
            document_chunk_ids=job.document_chunk_ids,
            created_by_bm25_build_job_id=job.id,
            on_index_created=link_index,
            before_finalize=stop_if_cancelled,
            session=session,
        )
        await corpus_bm25_build_jobs_repo.mark_corpus_bm25_build_job_stage(job, "persisting_artifact", session)
        if job.cancel_requested:
            return _read(await corpus_bm25_build_jobs_repo.mark_corpus_bm25_build_job_cancelled(job, session))
        return _read(await corpus_bm25_build_jobs_repo.mark_corpus_bm25_build_job_completed(job, metadata.id, session))
    except asyncio.CancelledError:
        refreshed = await corpus_bm25_build_jobs_repo.get_corpus_bm25_build_job_by_id(job_id, session)
        return _read(await corpus_bm25_build_jobs_repo.mark_corpus_bm25_build_job_cancelled(
            refreshed or job, session, "BM25 build cancellation requested"
        ))
    except Exception as exc:
        return _read(await corpus_bm25_build_jobs_repo.mark_corpus_bm25_build_job_failed(job, str(exc)[:500], session))


async def recover_interrupted_corpus_bm25_build_jobs_srvc(session: AsyncSession) -> None:
    """
    Recover interrupted BM25 build jobs.

    This function checks for any BM25 build jobs that were interrupted,
    typically due to an application restart, and marks them as failed.

    Args:
        session: The database session to use.

    Returns:
        None
    """
    for job in await corpus_bm25_build_jobs_repo.list_interrupted_corpus_bm25_build_jobs(session):
        if job.result_bm25_index_id is not None:
            try:
                await corpus_bm25_indices_repo.fail_corpus_bm25_index_build(
                    job.result_bm25_index_id,
                    "BM25 build interrupted by application restart.",
                    session,
                )
            except ValueError:
                pass
        await corpus_bm25_build_jobs_repo.mark_corpus_bm25_build_job_failed(
            job, "BM25 build interrupted by application restart.", session
        )
