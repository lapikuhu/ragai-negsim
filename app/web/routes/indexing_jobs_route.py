from fastapi import APIRouter, HTTPException, Response, status

from app.core.dependencies import AdminDep, Page, SessionDep
from app.schemas.indexing_jobs_schemas import IndexingJobCreate, IndexingJobDetail, IndexingJobQueued
from app.services import indexing_jobs_service

# Instantiate APIRouter for indexing job related endpoints
router = APIRouter(prefix="/indexing-jobs", tags=["indexing-jobs"])


def _raise_indexing_job_service_error(exc: ValueError) -> None:
    """
    Helper function to convert ValueErrors from the indexing jobs service 
    layer into HTTPExceptions with appropriate status codes.
        Args:
            exc: The ValueError exception to convert.
        Raises:
            HTTPException: The HTTP exception with the appropriate status 
            code and detail.
    """
    detail = str(exc)
    if detail in {
        "Corpus not found",
        "Chunking profile not found",
        "Vector store not found",
        "Indexing job not found",
    }:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc

### ---------------------- INDEXING JOB CREATE --------------------- ###
@router.post("/", response_model=IndexingJobQueued, status_code=status.HTTP_202_ACCEPTED)
async def create_indexing_job(
    job_in: IndexingJobCreate,
    session: SessionDep,
    _admin: AdminDep,
) -> IndexingJobQueued:
    """
    Create an indexing job endpoint.
        Args:
            job_in: The data to create the indexing job with.
            session: The database session.
            _admin: The admin dependency.
        Returns:
            An IndexingJobQueued object containing the queued indexing job data.
        Raises:
            HTTPException: If the indexing job cannot be created due to validation
            errors or other constraints, with a 409 status code and error detail.
    """
    try:
        queued = await indexing_jobs_service.queue_indexing_job_srvc(job_in, session)
    except ValueError as exc:
        _raise_indexing_job_service_error(exc)

    indexing_jobs_service.start_indexing_job_task(queued.id)
    return queued

### ---------------------- INDEXING JOB LIST ----------------------- ###
@router.get("/", response_model=list[IndexingJobQueued], status_code=status.HTTP_200_OK)
async def list_indexing_jobs(
    session: SessionDep,
    _admin: AdminDep,
    page: Page,
    status_filter: str | None = None,
    corpus_id: int | None = None,
) -> list[IndexingJobQueued]:
    """
    List indexing jobs endpoint.
        Args:
            session: The database session.
            _admin: The admin dependency.
            page: The pagination parameters.
            status_filter: Optional status to filter indexing jobs by.
            corpus_id: Optional corpus ID to filter indexing jobs by.
        Returns:
            A list of IndexingJobQueued objects containing the indexing 
            job data.
    """
    return [
        IndexingJobQueued(**job.model_dump())
        for job in await indexing_jobs_service.list_indexing_jobs_srvc(
            session,
            skip=page["skip"],
            limit=page["limit"],
            status=status_filter,
            corpus_id=corpus_id,
        )
    ]

### -------------------- ACTIVE INDEXING JOB GET ------------------- ###
@router.get("/active", response_model=IndexingJobDetail, status_code=status.HTTP_200_OK)
async def get_active_indexing_job(
    session: SessionDep,
    _admin: AdminDep,
) -> IndexingJobDetail | Response:
    """
    Get the active indexing job endpoint.
        Args:
            session: The database session.
            _admin: The admin dependency.
        Returns:
            An IndexingJobDetail object containing the active indexing job data,
            or a 204 No Content response if no active job is found.
    """
    job = await indexing_jobs_service.get_active_indexing_job_srvc(session)
    if job is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return job

### -------------------- INDEXING JOB DETAIL GET ------------------- ###
@router.get("/{job_id}", response_model=IndexingJobDetail, status_code=status.HTTP_200_OK)
async def get_indexing_job_detail(
    job_id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> IndexingJobDetail:
    """
    Get indexing job detail endpoint.
        Args:
            job_id: The ID of the indexing job to retrieve.
            session: The database session.
            _admin: The admin dependency.
        Returns:
            An IndexingJobDetail object containing the indexing job data.
        Raises:
            HTTPException: If the indexing job is not found, with a 404 status
            code and error detail.
    """
    try:
        return await indexing_jobs_service.get_indexing_job_detail_srvc(job_id, session)
    except ValueError as exc:
        _raise_indexing_job_service_error(exc)


@router.post("/{job_id}/cancel", response_model=IndexingJobDetail, status_code=status.HTTP_200_OK)
async def cancel_indexing_job(
    job_id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> IndexingJobDetail:
    """
    Cancel a queued or running indexing job.
    """
    try:
        return await indexing_jobs_service.cancel_indexing_job_srvc(job_id, session)
    except ValueError as exc:
        _raise_indexing_job_service_error(exc)
