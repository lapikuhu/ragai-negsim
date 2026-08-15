import asyncio

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.users import User
from app.repositories import (
    chunking_profiles_repo,
    corpus_bm25_build_jobs_repo, #as repository,
    corpus_bm25_indices_repo,
    corpus_repo,
    document_chunks_repo,
    full_corpus_index_pipe_jobs_repo,
    name_reservations_repo,
)
from app.schemas.corpus_bm25_build_jobs_schemas import (
    CorpusBm25BuildJobCreate,
    CorpusBm25BuildJobQueueRequest,
    CorpusBm25BuildJobRead,
    CorpusBm25BuildJobRetryRequest,
)
from app.services.corpus_bm25_indices_service import build_corpus_bm25_index_from_snapshot_srvc
from app.services.corpus_bm25_indices_service import delete_corpus_bm25_index_srvc
from app.services.helpers import _persisted_id
from app.services.corpus_chunk_sets_service import get_corpus_chunk_set_snapshot_srvc


CHANGED_SET_MESSAGE = (
    "The corpus chunk set changed since the job was queued. "
    "Retry to build the current snapshot."
)


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


async def ensure_corpus_bm25_index_name_available_srvc(
    name: str,
    session: AsyncSession,
) -> str:
    """
    Normalize a BM25 artifact name and reject an existing artifact.

    Args:
        name: The requested BM25 artifact name.
        session: The database session.
    Returns:
        str: The normalized BM25 artifact name.
    """
    normalized = name.strip()
    if len(normalized) < 3:
        raise CorpusBm25BuildJobConflictError(
            "BM25 index name must contain at least 3 characters"
        )
    existing = await corpus_bm25_indices_repo.get_corpus_bm25_index_metadata_by_name(
        normalized,
        session,
    )
    if existing is not None:
        raise CorpusBm25BuildJobConflictError("BM25 index name already exists or is reserved")
    if await corpus_bm25_build_jobs_repo.has_active_corpus_bm25_build_job_name(
        normalized, session
    ) or await full_corpus_index_pipe_jobs_repo.has_active_full_pipe_bm25_name_reservation(
        normalized, session
    ):
        raise CorpusBm25BuildJobConflictError("BM25 index name already exists or is reserved")
    return normalized


async def queue_corpus_bm25_build_job_for_requester_id_srvc(
    request: CorpusBm25BuildJobQueueRequest,
    requested_by_user_id: int,
    session: AsyncSession,
) -> CorpusBm25BuildJobRead:
    """
    Queue a BM25 build using an already persisted requester identity.
    Args:
        request: The CorpusBm25BuildJobQueueRequest containing the job 
            details.
        requested_by_user_id: The ID of the user requesting the job.
        session: The database session.
    Returns:
        CorpusBm25BuildJobRead: The created BM25 build job.
    Raises:
        CorpusBm25BuildJobNotFoundError: If the corpus or chunking profile
            is not found.
        CorpusBm25BuildJobConflictError: If there are no persisted chunks
            available for the corpus and chunking profile.
    """
    requested_name = request.requested_artifact_name.strip()
    # Reserve the name to prevent jobs with the same name from being queued concurrently
    await name_reservations_repo.lock_name_reservation(
        "corpus-bm25-artifact",
        requested_name,
        session,
    )
    artifact_name = await ensure_corpus_bm25_index_name_available_srvc(
        requested_name,
        session,
    )
    try:
        snapshot = await get_corpus_chunk_set_snapshot_srvc(
            request.corpus_chunk_set_id, session
        )
    except ValueError as exc:
        raise CorpusBm25BuildJobNotFoundError("Corpus chunk set not found") from exc
    if not snapshot.document_chunk_ids:
        raise CorpusBm25BuildJobConflictError(
            "The selected corpus chunk set is empty"
        )
    chunk_ids = list(snapshot.document_chunk_ids)
    chunks = await document_chunks_repo.get_corpus_chunk_set_document_chunks_by_ids(
        snapshot.chunk_set.id, chunk_ids, session
    )
    # Build the job
    job = await corpus_bm25_build_jobs_repo.create_corpus_bm25_build_job(
        CorpusBm25BuildJobCreate(
            requested_artifact_name=artifact_name,
            corpus_id=snapshot.chunk_set.corpus_id,
            chunking_profile_id=_persisted_id(
                snapshot.chunk_set.chunking_profile_id, "Chunking profile"
            ),
            corpus_chunk_set_id=snapshot.chunk_set.id,
            corpus_chunk_set_revision=snapshot.chunk_set.revision,
            corpus_chunk_set_checksum=snapshot.chunk_set.document_chunk_ids_checksum,
            requested_by_user_id=requested_by_user_id,
            document_chunk_ids=chunk_ids,
            document_chunk_ids_checksum=snapshot.chunk_set.document_chunk_ids_checksum,
            distinct_document_count=len({chunk.raw_document_id for chunk in chunks}),
            chunk_count=len(chunk_ids),
        ),
        session,
    )
    return _read(job)


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
    return await queue_corpus_bm25_build_job_for_requester_id_srvc(
        request,
        _persisted_id(current_user.id, "User"),
        session,
    )


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


async def rollback_parent_owned_corpus_bm25_job_srvc(
    *,
    job_id: int,
    full_pipe_job_id: int,
    detail: str,
    session: AsyncSession,
    delete_artifact: bool = True,
    terminalize: bool = True,
) -> CorpusBm25BuildJobRead:
    """
    Delete a parent-owned result and make its child history truthful.

    Args:
        job_id: The ID of the BM25 build job to rollback.
        full_pipe_job_id: The ID of the full corpus index pipe job that owns 
            the BM25 build job.
        detail: The detail message for the rollback.
        session: The database session.
        delete_artifact: Whether to delete the BM25 index artifact.
        terminalize: Whether to mark the job as rolled back or append 
            rollback details. Default is True.
    Returns:
        CorpusBm25BuildJobRead: The updated BM25 build job after rollback.
    Raises:
        CorpusBm25BuildJobNotFoundError: If the job is not found.
        CorpusBm25BuildJobConflictError: If the job cannot be rolled back.
    """
    job = await corpus_bm25_build_jobs_repo.get_corpus_bm25_build_job_by_id(
        job_id,
        session,
    )
    if job is None:
        raise CorpusBm25BuildJobNotFoundError("BM25 build job not found")

    if job.status in {"queued", "running"}:
        job = await corpus_bm25_build_jobs_repo.request_corpus_bm25_build_job_cancel(
            job,
            session,
        )
        if job.status == "running":
            return _read(job)

    metadata = None
    result_index_id = job.result_bm25_index_id
    if delete_artifact:
        if result_index_id is not None:
            metadata = await corpus_bm25_indices_repo.get_corpus_bm25_index_metadata_by_id(
                result_index_id,
                session,
            )
        if metadata is None:
            metadata = (
                await corpus_bm25_indices_repo.get_corpus_bm25_index_metadata_by_full_pipe_job_id(
                    full_pipe_job_id,
                    session,
                )
            )

    if metadata is not None:
        owner_id = metadata.created_by_full_corpus_index_pipe_job_id
        if owner_id is None and result_index_id == metadata.id:
            await corpus_bm25_indices_repo.link_corpus_bm25_index_to_full_pipe_job(
                metadata.id,
                full_pipe_job_id,
                session,
            )
        elif owner_id != full_pipe_job_id:
            raise CorpusBm25BuildJobConflictError(
                "BM25 artifact belongs to another full corpus pipeline job"
            )
        if job.result_bm25_index_id is not None:
            job = await corpus_bm25_build_jobs_repo.clear_corpus_bm25_build_job_result(
                job,
                session,
            )
        await delete_corpus_bm25_index_srvc(metadata, session)

    if terminalize and job.status == "completed":
        job = await corpus_bm25_build_jobs_repo.mark_corpus_bm25_build_job_rolled_back(
            job,
            detail,
            session,
        )
    elif terminalize and job.status in {"failed", "cancelled"}:
        job = await corpus_bm25_build_jobs_repo.append_corpus_bm25_build_job_rollback_detail(
            job,
            detail,
            session,
        )
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
    if old.corpus_chunk_set_id is None:
        raise CorpusBm25BuildJobConflictError(
            "The original corpus chunk set no longer exists"
        )
    return await queue_corpus_bm25_build_job_srvc(
        CorpusBm25BuildJobQueueRequest(
            requested_artifact_name=request.requested_artifact_name,
            corpus_chunk_set_id=old.corpus_chunk_set_id,
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
    if job.corpus_chunk_set_id is None:
        return _read(await corpus_bm25_build_jobs_repo.mark_corpus_bm25_build_job_failed(
            job,
            "The selected corpus chunk set no longer exists",
            session,
        ))
    # Check against the corpus chunk set snapshot to ensure that the job is still valid
    try:
        snapshot = await get_corpus_chunk_set_snapshot_srvc(
            job.corpus_chunk_set_id, session
        )
    except ValueError:
        return _read(await corpus_bm25_build_jobs_repo.mark_corpus_bm25_build_job_failed(
            job, "The selected corpus chunk set no longer exists", session
        ))
    if (
        snapshot.chunk_set.revision != job.corpus_chunk_set_revision
        or snapshot.chunk_set.document_chunk_ids_checksum
        != job.corpus_chunk_set_checksum
        or snapshot.document_chunk_ids != job.document_chunk_ids
    ):
        return _read(await corpus_bm25_build_jobs_repo.mark_corpus_bm25_build_job_failed(
            job, CHANGED_SET_MESSAGE, session
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
            corpus_chunk_set_id=job.corpus_chunk_set_id,
            corpus_chunk_set_revision=job.corpus_chunk_set_revision,
            corpus_chunk_set_checksum=job.corpus_chunk_set_checksum,
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
