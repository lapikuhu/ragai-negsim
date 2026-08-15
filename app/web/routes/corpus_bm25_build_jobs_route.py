from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.core.dependencies import AdminDep, Page, SessionDep
from app.schemas.corpus_bm25_build_jobs_schemas import (
    CorpusBm25BuildJobQueueRequest,
    CorpusBm25BuildJobRead,
    CorpusBm25BuildJobRetryRequest,
    CorpusBm25IndexNameAvailability,
)
from app.services import corpus_bm25_build_jobs_service as service
from app.services.corpus_bm25_build_coordinator import wake_corpus_bm25_build_coordinator
from app.services.corpus_bm25_build_jobs_service import (
    CorpusBm25BuildJobConflictError,
    CorpusBm25BuildJobNotFoundError,
)

# Instantiate the router for corpus BM25 build jobs with a prefix and tags for documentation
router = APIRouter(prefix="/corpus-bm25-build-jobs", tags=["corpus-bm25-build-jobs"])


def _raise(exc: ValueError) -> None:
    """
    Raise an HTTPException based on the type of exception provided. 
    If the exception is a CorpusBm25BuildJobNotFoundError, it raises a 
    404 Not Found error. If it's a CorpusBm25BuildJobConflictError, 
    it raises a 409 Conflict error. The detail of the exception is 
    included in the response.
    """
    code = status.HTTP_404_NOT_FOUND if isinstance(exc, CorpusBm25BuildJobNotFoundError) else status.HTTP_409_CONFLICT
    raise HTTPException(status_code=code, detail=str(exc)) from exc

### ---------------------- BM25 NAME AVAILABILITY GET --------------------- ###
@router.get("/name-availability", 
            response_model=CorpusBm25IndexNameAvailability,
            status_code=status.HTTP_200_OK,
            )
async def get_corpus_bm25_index_name_availability(
    name: str,
    session: SessionDep,
    _admin: AdminDep,
) -> CorpusBm25IndexNameAvailability:
    """
    Check the availability of a corpus BM25 index name.

    Args:
        name (str): The name of the corpus BM25 index to check.
        session (SessionDep): The database session dependency.
        _admin (AdminDep): The admin dependency for authorization.
    Returns:
        CorpusBm25IndexNameAvailability: The availability status of the corpus 
        BM25 index name.
    """
    try:
        normalized = await service.ensure_corpus_bm25_index_name_available_srvc(
            name, session
        )
    except CorpusBm25BuildJobConflictError as exc:
        return CorpusBm25IndexNameAvailability(
            name=name.strip(), available=False, reason=str(exc)
        )
    return CorpusBm25IndexNameAvailability(name=normalized, available=True)

### ------------------------ QUEUE BM25 JOB ------------------------ ###
@router.post("/", 
             response_model=CorpusBm25BuildJobRead, 
             status_code=status.HTTP_202_ACCEPTED)
async def queue_corpus_bm25_build_job(request: CorpusBm25BuildJobQueueRequest, 
                                      session: SessionDep, 
                                      admin: AdminDep) -> CorpusBm25BuildJobRead:
    """
    Queue a new corpus BM25 build job.
    
    Args:
        request (CorpusBm25BuildJobQueueRequest): The request body containing 
            the details of the corpus BM25 build job to be queued.
        session (SessionDep): The database session dependency.
        admin (AdminDep): The admin dependency for authorization.
    Returns:
        CorpusBm25BuildJobRead: The details of the queued corpus BM25 
        build job.
    """

    try:
        queued = await service.queue_corpus_bm25_build_job_srvc(request, admin, session)
    except (CorpusBm25BuildJobNotFoundError, CorpusBm25BuildJobConflictError) as exc:
        _raise(exc)
    wake_corpus_bm25_build_coordinator()
    return queued

### ------------------------ LIST BM25 JOBS ------------------------ ###
@router.get("/", 
            response_model=list[CorpusBm25BuildJobRead],
            status_code=status.HTTP_200_OK)
async def list_corpus_bm25_build_jobs(
    session: SessionDep,
    _admin: AdminDep,
    page: Page,
    corpus_id: int | None = None,
    status_filter: Literal["queued", "running", "completed", "failed", "cancelled"] | None = Query(default=None, alias="status"),
):
    """
    List corpus BM25 build jobs.

    Args:
        session (SessionDep): The database session dependency.
        _admin (AdminDep): The admin dependency for authorization.
        page (Page): Pagination information.
        corpus_id (int | None): Filter by corpus ID.
        status_filter (Literal["queued", "running", "completed", "failed", 
            "cancelled"] | None): Filter by job status.
    Returns:
        list[CorpusBm25BuildJobRead]: A list of corpus BM25 build jobs.
    """
    return await service.list_corpus_bm25_build_jobs_srvc(
        session=session, skip=page["skip"], limit=page["limit"], corpus_id=corpus_id, status=status_filter
    )

### ---------------------- GET BM25 JOB BY ID ---------------------- ###
@router.get("/{job_id}", 
            response_model=CorpusBm25BuildJobRead,
            status_code=status.HTTP_200_OK)
async def get_corpus_bm25_build_job(job_id: int, 
                                    session: SessionDep, 
                                    _admin: AdminDep) -> CorpusBm25BuildJobRead | None:
    """
    Get a corpus BM25 build job by its ID.

    Args:
        job_id (int): The ID of the corpus BM25 build job to retrieve.
        session (SessionDep): The database session dependency.
        _admin (AdminDep): The admin dependency for authorization.
    Returns:
        CorpusBm25BuildJobRead | None: The details of the corpus BM25 build 
        job.
    """
    try:
        return await service.get_corpus_bm25_build_job_srvc(job_id, session)
    except CorpusBm25BuildJobNotFoundError as exc:
        _raise(exc)

### -------------------- CANCEL BM25 JOB BY ID --------------------- ###
@router.post("/{job_id}/cancel", 
             response_model=CorpusBm25BuildJobRead,
             status_code=status.HTTP_200_OK)
async def cancel_corpus_bm25_build_job(job_id: int, 
                                       session: SessionDep, 
                                       _admin: AdminDep):
    """
    Cancel a corpus BM25 build job by its ID.

    Args:
        job_id (int): The ID of the corpus BM25 build job to cancel.
        session (SessionDep): The database session dependency.
        _admin (AdminDep): The admin dependency for authorization.
    Returns:
        CorpusBm25BuildJobRead: The details of the cancelled corpus BM25 
        build job.
    """
    try:
        return await service.cancel_corpus_bm25_build_job_srvc(job_id, session)
    except (CorpusBm25BuildJobNotFoundError, CorpusBm25BuildJobConflictError) as exc:
        _raise(exc)

### ---------------------- RETRY BM25 JOB BY ID -------------------- ###
@router.post("/{job_id}/retry", 
             response_model=CorpusBm25BuildJobRead, 
             status_code=status.HTTP_202_ACCEPTED)
async def retry_corpus_bm25_build_job(job_id: int, 
                                      request: CorpusBm25BuildJobRetryRequest, 
                                      session: SessionDep, 
                                      admin: AdminDep):
    """
    Retry a corpus BM25 build job by its ID.

    Args:
        job_id (int): The ID of the corpus BM25 build job to retry.
        request (CorpusBm25BuildJobRetryRequest): The retry request payload.
        session (SessionDep): The database session dependency.
        admin (AdminDep): The admin dependency for authorization.
    Returns:
        CorpusBm25BuildJobRead: The details of the retried corpus BM25 
        build job.
    """
    try:
        queued = await service.retry_corpus_bm25_build_job_srvc(job_id, request, admin, session)
    except (CorpusBm25BuildJobNotFoundError, CorpusBm25BuildJobConflictError) as exc:
        _raise(exc)
    wake_corpus_bm25_build_coordinator()
    return queued
