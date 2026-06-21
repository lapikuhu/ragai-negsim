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

# Instantiate the API router for knowledge graph index-related endpoints
router = APIRouter(
    prefix="/knowledge-graph-indexes",
    tags=["knowledge-graph-indexes"],
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
    if detail in {"Knowledge graph not found", "Corpus index not found"}:
        raise HTTPException(status_code=404, detail=detail) from exc
    raise HTTPException(status_code=409, detail=detail) from exc

### -------------------- KNOWLEDGE GRAPH CREATE -------------------- ###
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
    """
    Create a new knowledge graph index.
    Args:
        graph_in (KnowledgeGraphIndexCreate): The data for the knowledge 
            graph index to create.
        session (SessionDep): The database session dependency.
        _admin (AdminDep): The admin dependency to ensure the user has 
            admin privileges.
    Returns:
        KnowledgeGraphIndexReadWithUsage: The created knowledge graph 
        index with its usage details.
    Raises:
        HTTPException: If there is a conflict or error during the creation 
        of the knowledge graph index
    """
    try:
        return await knowledge_graph_indices_service.create_knowledge_graph_index_srvc(
            graph_in,
            session,
        )
    except ValueError as exc:
        _raise_service_error(exc)

### -------------------- KNOWLEDGE GRAPH LIST ---------------------- ###
@router.get("/", response_model=list[KnowledgeGraphIndexReadWithUsage])
async def list_knowledge_graph_indices(
    session: SessionDep,
    _admin: AdminDep,
    page: Page,
    corpus_index_id: int | None = None,
    status_filter: str | None = None,
) -> list[KnowledgeGraphIndexReadWithUsage]:
    """
    List knowledge graph indices with optional filtering and pagination.
    Args:
        session (SessionDep): The database session dependency.
        _admin (AdminDep): The admin dependency to ensure the user has 
            admin privileges.
        page (Page): The pagination parameters.
        corpus_index_id (int | None): Optional filter by corpus index ID.
        status_filter (str | None): Optional filter by status.
    Returns:
        list[KnowledgeGraphIndexReadWithUsage]: A list of knowledge graph 
        indices with their usage details.
    """
    return await knowledge_graph_indices_service.list_knowledge_graph_indices_srvc(
        session,
        skip=page["skip"],
        limit=page["limit"],
        corpus_index_id=corpus_index_id,
        status=status_filter,
    )

### ------------------- KNOWLEDGE GRAPH GET BY ID ------------------ ###
@router.get("/{graph_id}", response_model=KnowledgeGraphIndexReadWithUsage)
async def get_knowledge_graph_index(
    graph: AdminKnowledgeGraphIndexDep,
    session: SessionDep,
) -> KnowledgeGraphIndexReadWithUsage:
    """
    Get a knowledge graph index by its ID.
    Args:
        graph (AdminKnowledgeGraphIndexDep): The knowledge graph index 
            dependency.
        session (SessionDep): The database session dependency.
    Returns:
        KnowledgeGraphIndexReadWithUsage: The knowledge graph index with its usage details.
    """
    return await knowledge_graph_indices_service.get_knowledge_graph_index_srvc(
        graph,
        session,
    )

### --------------------- KNOWLEDGE GRAPH UPDATE ------------------- ###
@router.patch("/{graph_id}", response_model=KnowledgeGraphIndexReadWithUsage)
async def update_knowledge_graph_index(
    graph_in: KnowledgeGraphIndexUpdate,
    graph: AdminKnowledgeGraphIndexDep,
    session: SessionDep,
) -> KnowledgeGraphIndexReadWithUsage:
    """
    Update a knowledge graph index.
    Args:
        graph_in (KnowledgeGraphIndexUpdate): The data for updating the 
        knowledge graph index.
        graph (AdminKnowledgeGraphIndexDep): The knowledge graph index 
            dependency.
        session (SessionDep): The database session dependency.
    Returns:
        KnowledgeGraphIndexReadWithUsage: The updated knowledge graph 
        index with its usage details.
    """
    try:
        return await knowledge_graph_indices_service.update_knowledge_graph_index_srvc(
            graph,
            graph_in,
            session,
        )
    except ValueError as exc:
        _raise_service_error(exc)

### --------------------- KNOWLEDGE GRAPH DELETE ------------------- ###    
@router.delete("/{graph_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_graph_index(
    graph: AdminKnowledgeGraphIndexDep,
    session: SessionDep,
) -> Response:
    """
    Delete a knowledge graph index.
    Args:
        graph (AdminKnowledgeGraphIndexDep): The knowledge graph index 
            dependency.
        session (SessionDep): The database session dependency.
    Returns:
        Response: An empty response with HTTP 204 status code.
    """
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
    """
    Queue a knowledge graph build job.
    Args:
        graph (AdminKnowledgeGraphIndexDep): The knowledge graph index 
            dependency.
        session (SessionDep): The database session dependency.
        rebuild (bool): Whether to rebuild the knowledge graph index.
    Returns:
        KnowledgeGraphBuildJobRead: The knowledge graph build job details.
    """
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

### -------------------- KNOWLEDGE GRAPH BUILD --------------------- ###
@router.post(
    "/{graph_id}/build",
    response_model=KnowledgeGraphBuildJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def build_knowledge_graph(
    graph: AdminKnowledgeGraphIndexDep,
    session: SessionDep,
) -> KnowledgeGraphBuildJobRead:
    """
    Build a knowledge graph index.
    Args:
        graph (AdminKnowledgeGraphIndexDep): The knowledge graph index 
            dependency.
        session (SessionDep): The database session dependency.
    Returns:
        KnowledgeGraphBuildJobRead: The knowledge graph build job details.
    """
    return await _queue_build(graph, session, rebuild=False)

### -------------------- KNOWLEDGE GRAPH REBUILD ------------------- ###
@router.post(
    "/{graph_id}/rebuild",
    response_model=KnowledgeGraphBuildJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def rebuild_knowledge_graph(
    graph: AdminKnowledgeGraphIndexDep,
    session: SessionDep,
) -> KnowledgeGraphBuildJobRead:
    """
    Rebuild a knowledge graph index.
    Args:
        graph (AdminKnowledgeGraphIndexDep): The knowledge graph index 
        dependency.
        session (SessionDep): The database session dependency.
    Returns:
        KnowledgeGraphBuildJobRead: The knowledge graph build job details.
    """
    return await _queue_build(graph, session, rebuild=True)

