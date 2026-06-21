from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import AdminDep, Page, SessionDep
from app.schemas.knowledge_graph_build_jobs_schemas import (
    KnowledgeGraphBuildJobRead,
)
from app.services import knowledge_graph_builds_service

# Instantiate the API router for knowledge graph build job-related endpoints
router = APIRouter(
    prefix="/knowledge-graph-build-jobs",
    tags=["knowledge-graph-build-jobs"],
)

# Helper candidate
def _raise_service_error(exc: ValueError) -> None:
    """
    Raise an HTTPException based on the ValueError received.
    Args:
        exc (ValueError): The exception to be converted into an 
        `HTTPException`.
    Raises:
        HTTPException: The corresponding HTTP exception based on the 
        error detail.
    """
    detail = str(exc)
    code = 404 if detail == "Knowledge graph build job not found" else 409
    raise HTTPException(status_code=code, detail=detail) from exc

### ---------------- KNOWLEDGE GRAPH BUILD JOBS LIST --------------- ###
@router.get("/", response_model=list[KnowledgeGraphBuildJobRead])
async def list_knowledge_graph_build_jobs(
    session: SessionDep,
    _admin: AdminDep,
    page: Page,
    graph_id: int | None = None,
    status_filter: str | None = None,
) -> list[KnowledgeGraphBuildJobRead]:
    """
    List knowledge graph build jobs with optional filtering and pagination.
    Args:
        session (SessionDep): The database session dependency.
        _admin (AdminDep): The admin dependency to ensure the user has admin privileges.
        page (Page): The pagination parameters.
        graph_id (int | None): Optional filter by knowledge graph index ID.
        status_filter (str | None): Optional filter by job status.
    Returns:
        list[KnowledgeGraphBuildJobRead]: A list of knowledge graph build jobs.
    """
    return await knowledge_graph_builds_service.list_knowledge_graph_build_jobs_srvc(
        session,
        skip=page["skip"],
        limit=page["limit"],
        graph_id=graph_id,
        status=status_filter,
    )

### ------------- KNOWLEDGE GRAPH BUILD JOB GET BY ID -------------- ###
@router.get("/{job_id}", response_model=KnowledgeGraphBuildJobRead)
async def get_knowledge_graph_build_job(
    job_id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> KnowledgeGraphBuildJobRead:
    """
    Get a knowledge graph build job by its ID.
    Args:
        job_id (int): The ID of the knowledge graph build job.
        session (SessionDep): The database session dependency.
        _admin (AdminDep): The admin dependency to ensure the user has 
            admin privileges.
    Returns:
        KnowledgeGraphBuildJobRead: The knowledge graph build job details.
    """
    try:
        return await knowledge_graph_builds_service.get_knowledge_graph_build_job_srvc(
            job_id,
            session,
        )
    except ValueError as exc:
        _raise_service_error(exc)

### ------------------ KNOWLEDGE GRAPH BUILD JOB CANCEL ------------ ###
@router.post(
    "/{job_id}/cancel",
    response_model=KnowledgeGraphBuildJobRead,
    status_code=status.HTTP_200_OK,
)
async def cancel_knowledge_graph_build_job(
    job_id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> KnowledgeGraphBuildJobRead:
    """
    Cancel a knowledge graph build job by its ID.
    Args:
        job_id (int): The ID of the knowledge graph build job.
        session (SessionDep): The database session dependency.
        _admin (AdminDep): The admin dependency to ensure the user has 
            admin privileges.
    Returns:
        KnowledgeGraphBuildJobRead: The updated knowledge graph build job details.
    """
    try:
        return await knowledge_graph_builds_service.cancel_knowledge_graph_build_job_srvc(
            job_id,
            session,
        )
    except ValueError as exc:
        _raise_service_error(exc)

