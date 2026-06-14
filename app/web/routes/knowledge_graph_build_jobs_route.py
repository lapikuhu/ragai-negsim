from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import AdminDep, Page, SessionDep
from app.schemas.knowledge_graph_build_jobs_schemas import (
    KnowledgeGraphBuildJobRead,
)
from app.services import knowledge_graph_builds_service


router = APIRouter(
    prefix="/knowledge-graph-build-jobs",
    tags=["knowledge-graph-build-jobs"],
)


def _raise_service_error(exc: ValueError) -> None:
    detail = str(exc)
    code = 404 if detail == "Knowledge graph build job not found" else 409
    raise HTTPException(status_code=code, detail=detail) from exc


@router.get("/", response_model=list[KnowledgeGraphBuildJobRead])
async def list_knowledge_graph_build_jobs(
    session: SessionDep,
    _admin: AdminDep,
    page: Page,
    graph_id: int | None = None,
    status_filter: str | None = None,
) -> list[KnowledgeGraphBuildJobRead]:
    return await knowledge_graph_builds_service.list_knowledge_graph_build_jobs_srvc(
        session,
        skip=page["skip"],
        limit=page["limit"],
        graph_id=graph_id,
        status=status_filter,
    )


@router.get("/{job_id}", response_model=KnowledgeGraphBuildJobRead)
async def get_knowledge_graph_build_job(
    job_id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> KnowledgeGraphBuildJobRead:
    try:
        return await knowledge_graph_builds_service.get_knowledge_graph_build_job_srvc(
            job_id,
            session,
        )
    except ValueError as exc:
        _raise_service_error(exc)


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
    try:
        return await knowledge_graph_builds_service.cancel_knowledge_graph_build_job_srvc(
            job_id,
            session,
        )
    except ValueError as exc:
        _raise_service_error(exc)

