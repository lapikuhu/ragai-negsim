from fastapi import APIRouter, HTTPException, Response, status

from app.core.dependencies import AdminDep, Page, SessionDep
from app.schemas.full_corpus_index_pipe_jobs_schemas import FullCorpusIndexPipeJobCreate, FullCorpusIndexPipeJobDetail, FullCorpusIndexPipeJobQueued
from app.services import full_corpus_index_pipe_job

# Instantiate APIRouter for full corpus index pipe job related endpoints
router = APIRouter(prefix="/full-corpus-index-pipe-jobs", tags=["full-corpus-index-pipe-jobs"])


def _raise_full_corpus_index_pipe_job_service_error(exc: ValueError) -> None:
    """
    Helper function to convert ValueErrors from the full corpus index pipe jobs service 
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
        "Full corpus index pipe job not found",
    }:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc

### -------------- FULL CORPUS INDEX PIPE JOB CREATE -------------- ###
@router.post("/", response_model=FullCorpusIndexPipeJobQueued, status_code=status.HTTP_202_ACCEPTED)
async def create_full_corpus_index_pipe_job(
    job_in: FullCorpusIndexPipeJobCreate,
    session: SessionDep,
    _admin: AdminDep,
) -> FullCorpusIndexPipeJobQueued:
    """
    Create a full corpus index pipe job endpoint.
        Args:
            job_in: The data to create the full corpus index pipe job with.
            session: The database session.
            _admin: The admin dependency.
        Returns:
            A FullCorpusIndexPipeJobQueued object containing the queued full corpus index pipe job data.
        Raises:
            HTTPException: If the full corpus index pipe job cannot be created due to validation
            errors or other constraints, with a 409 status code and error detail.
    """
    try:
        queued = await full_corpus_index_pipe_job.queue_full_corpus_index_pipe_job_srvc(job_in, session)
    except ValueError as exc:
        _raise_full_corpus_index_pipe_job_service_error(exc)

    full_corpus_index_pipe_job.start_full_corpus_index_pipe_job_task(queued.id)
    return queued

### --------------- FULL CORPUS INDEX PIPE JOB LIST --------------- ###
@router.get("/", response_model=list[FullCorpusIndexPipeJobQueued], status_code=status.HTTP_200_OK)
async def list_full_corpus_index_pipe_jobs(
    session: SessionDep,
    _admin: AdminDep,
    page: Page,
    status_filter: str | None = None,
    corpus_id: int | None = None,
) -> list[FullCorpusIndexPipeJobQueued]:
    """
    List full corpus index pipe jobs endpoint.
        Args:
            session: The database session.
            _admin: The admin dependency.
            page: The pagination parameters.
            status_filter: Optional status to filter full corpus index pipe jobs by.
            corpus_id: Optional corpus ID to filter full corpus index pipe jobs by.
        Returns:
            A list of FullCorpusIndexPipeJobQueued objects containing the full corpus index pipe job data.
    """
    return [
        FullCorpusIndexPipeJobQueued(**job.model_dump())
        for job in await full_corpus_index_pipe_job.list_full_corpus_index_pipe_jobs_srvc(
            session,
            skip=page["skip"],
            limit=page["limit"],
            status=status_filter,
            corpus_id=corpus_id,
        )
    ]

### ------------ ACTIVE FULL CORPUS INDEX PIPE JOB GET ------------ ###
@router.get("/active", response_model=FullCorpusIndexPipeJobDetail, status_code=status.HTTP_200_OK)
async def get_active_full_corpus_index_pipe_job(
    session: SessionDep,
    _admin: AdminDep,
) -> FullCorpusIndexPipeJobDetail | Response:
    """
    Get the active full corpus index pipe job endpoint.
        Args:
            session: The database session.
            _admin: The admin dependency.
        Returns:
            A FullCorpusIndexPipeJobDetail object containing the active full corpus index pipe job data,
            or a 204 No Content response if no active job is found.
    """
    job = await full_corpus_index_pipe_job.get_active_full_corpus_index_pipe_job_srvc(session)
    if job is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return job

### ------------ FULL CORPUS INDEX PIPE JOB DETAIL GET ------------ ###
@router.get("/{job_id}", response_model=FullCorpusIndexPipeJobDetail, status_code=status.HTTP_200_OK)
async def get_full_corpus_index_pipe_job_detail(
    job_id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> FullCorpusIndexPipeJobDetail:
    """
    Get full corpus index pipe job detail endpoint.
        Args:
            job_id: The ID of the full corpus index pipe job to retrieve.
            session: The database session.
            _admin: The admin dependency.
        Returns:
            A FullCorpusIndexPipeJobDetail object containing the full corpus index pipe job data.
        Raises:
            HTTPException: If the full corpus index pipe job is not found, with a 404 status
            code and error detail.
    """
    try:
        return await full_corpus_index_pipe_job.get_full_corpus_index_pipe_job_detail_srvc(job_id, session)
    except ValueError as exc:
        _raise_full_corpus_index_pipe_job_service_error(exc)


@router.post("/{job_id}/cancel", response_model=FullCorpusIndexPipeJobDetail, status_code=status.HTTP_200_OK)
async def cancel_full_corpus_index_pipe_job(
    job_id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> FullCorpusIndexPipeJobDetail:
    """
    Cancel a queued or running full corpus index pipe job.
    """
    try:
        return await full_corpus_index_pipe_job.cancel_full_corpus_index_pipe_job_srvc(job_id, session)
    except ValueError as exc:
        _raise_full_corpus_index_pipe_job_service_error(exc)
