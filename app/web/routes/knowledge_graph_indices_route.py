from fastapi import APIRouter, HTTPException, Response, status

from app.core.dependencies import (
    AdminDep,
    AdminKnowledgeGraphIndexDep,
    Page,
    SessionDep,
)
from app.schemas.knowledge_graph_build_jobs_schemas import (
    KnowledgeGraphBuildJobRead,
)
from app.schemas.knowledge_graph_indices_schemas import (
    KnowledgeGraphIndexCreate,
    KnowledgeGraphIndexReadWithUsage,
    KnowledgeGraphIndexUpdate,
)
from app.services import (
    knowledge_graph_builds_service,
    knowledge_graph_indices_service,
)


router = APIRouter(
    prefix="/knowledge-graph-indexes",
    tags=["knowledge-graph-indexes"],
)


def _raise_service_error(exc: ValueError) -> None:
    detail = str(exc)
    if detail in {"Knowledge graph not found", "Corpus index not found"}:
        raise HTTPException(status_code=404, detail=detail) from exc
    raise HTTPException(status_code=409, detail=detail) from exc


@router.post(
    "/",
    response_model=KnowledgeGraphIndexReadWithUsage,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_graph_index(
    graph_in: KnowledgeGraphIndexCreate,
    session: SessionDep,
    _admin: AdminDep,
) -> KnowledgeGraphIndexReadWithUsage:
    try:
        return await knowledge_graph_indices_service.create_knowledge_graph_index_srvc(
            graph_in,
            session,
        )
    except ValueError as exc:
        _raise_service_error(exc)


@router.get("/", response_model=list[KnowledgeGraphIndexReadWithUsage])
async def list_knowledge_graph_indices(
    session: SessionDep,
    _admin: AdminDep,
    page: Page,
    corpus_index_id: int | None = None,
    status_filter: str | None = None,
) -> list[KnowledgeGraphIndexReadWithUsage]:
    return await knowledge_graph_indices_service.list_knowledge_graph_indices_srvc(
        session,
        skip=page["skip"],
        limit=page["limit"],
        corpus_index_id=corpus_index_id,
        status=status_filter,
    )


@router.get("/{graph_id}", response_model=KnowledgeGraphIndexReadWithUsage)
async def get_knowledge_graph_index(
    graph: AdminKnowledgeGraphIndexDep,
    session: SessionDep,
) -> KnowledgeGraphIndexReadWithUsage:
    return await knowledge_graph_indices_service.get_knowledge_graph_index_srvc(
        graph,
        session,
    )


@router.patch("/{graph_id}", response_model=KnowledgeGraphIndexReadWithUsage)
async def update_knowledge_graph_index(
    graph_in: KnowledgeGraphIndexUpdate,
    graph: AdminKnowledgeGraphIndexDep,
    session: SessionDep,
) -> KnowledgeGraphIndexReadWithUsage:
    try:
        return await knowledge_graph_indices_service.update_knowledge_graph_index_srvc(
            graph,
            graph_in,
            session,
        )
    except ValueError as exc:
        _raise_service_error(exc)


@router.delete("/{graph_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_graph_index(
    graph: AdminKnowledgeGraphIndexDep,
    session: SessionDep,
) -> Response:
    try:
        await knowledge_graph_indices_service.delete_knowledge_graph_index_srvc(
            graph,
            session,
        )
    except ValueError as exc:
        _raise_service_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _queue_build(
    graph,
    session,
    *,
    rebuild: bool,
) -> KnowledgeGraphBuildJobRead:
    try:
        queued = await knowledge_graph_builds_service.queue_knowledge_graph_build_srvc(
            graph.id,
            session,
            rebuild=rebuild,
        )
    except ValueError as exc:
        _raise_service_error(exc)
    knowledge_graph_builds_service.start_knowledge_graph_build_task(queued.id)
    return queued


@router.post(
    "/{graph_id}/build",
    response_model=KnowledgeGraphBuildJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def build_knowledge_graph(
    graph: AdminKnowledgeGraphIndexDep,
    session: SessionDep,
) -> KnowledgeGraphBuildJobRead:
    return await _queue_build(graph, session, rebuild=False)


@router.post(
    "/{graph_id}/rebuild",
    response_model=KnowledgeGraphBuildJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def rebuild_knowledge_graph(
    graph: AdminKnowledgeGraphIndexDep,
    session: SessionDep,
) -> KnowledgeGraphBuildJobRead:
    return await _queue_build(graph, session, rebuild=True)

