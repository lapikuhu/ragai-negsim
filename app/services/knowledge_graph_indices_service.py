from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.knowledge_graph_indices import KnowledgeGraphIndex
from app.repositories import (
    corpus_indices_repo,
    document_chunks_repo,
    knowledge_graph_build_jobs_repo,
    knowledge_graph_indices_repo,
)
from app.schemas.knowledge_graph_indices_schemas import (
    KnowledgeGraphIndexCreate,
    KnowledgeGraphIndexReadWithUsage,
    KnowledgeGraphIndexUpdate,
)


async def _read_with_usage(
    graph: KnowledgeGraphIndex,
    session: AsyncSession,
) -> KnowledgeGraphIndexReadWithUsage:
    """
    Read a knowledge graph index and include its usage information, such 
    as associated RAG profiles, simulations, and active build job.
    Args:
        graph: The KnowledgeGraphIndex instance to read.
        session: The database session.
    Returns:
        A KnowledgeGraphIndexReadWithUsage instance containing the 
        graph's details and usage information.
    """
    if graph.id is None:
        raise ValueError("Knowledge graph must be persisted")
    profile_ids, simulation_ids = (
        await knowledge_graph_indices_repo.get_knowledge_graph_usage(
            graph.id,
            session,
        )
    )
    active_job = (
        await knowledge_graph_build_jobs_repo.get_active_knowledge_graph_build_job(
            graph.id,
            session,
        )
    )
    return KnowledgeGraphIndexReadWithUsage(
        **graph.model_dump(),
        rag_profile_ids=profile_ids,
        simulation_ids=simulation_ids,
        active_job_id=active_job.id if active_job is not None else None,
    )


async def create_knowledge_graph_index_srvc(
    graph_in: KnowledgeGraphIndexCreate,
    session: AsyncSession,
) -> KnowledgeGraphIndexReadWithUsage:
    """
    Create a new knowledge graph index after validating the associated 
    corpus index and its chunks.
    Args:
        graph_in: The KnowledgeGraphIndexCreate instance containing the 
            graph details.
        session: The database session.
    Returns:
        A KnowledgeGraphIndexReadWithUsage instance representing the newly 
        created knowledge graph index.
    Raises:
        ValueError: If the associated corpus index is not found, not built, 
        or has no indexed chunks.
    """
    corpus_index = await corpus_indices_repo.get_corpus_index_by_id(
        graph_in.corpus_index_id,
        session,
    )
    if corpus_index is None:
        raise ValueError("Corpus index not found")
    if corpus_index.status != "built":
        raise ValueError("Knowledge graph requires a built corpus index")
    chunks = await document_chunks_repo.list_document_chunks_for_corpus_index(
        graph_in.corpus_index_id,
        session,
    )
    if not chunks:
        raise ValueError("Corpus index has no indexed chunks")
    graph = await knowledge_graph_indices_repo.create_knowledge_graph_index(
        graph_in,
        session,
    )
    return await _read_with_usage(graph, session)


async def list_knowledge_graph_indices_srvc(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 20,
    corpus_index_id: int | None = None,
    status: str | None = None,
) -> list[KnowledgeGraphIndexReadWithUsage]:
    """
    List knowledge graph indices with optional filtering by corpus index
    ID and status, including usage information for each graph.
    Args:
        session: The database session.
        skip: The number of records to skip for pagination.
        limit: The maximum number of records to return.
        corpus_index_id: Optional filter for corpus index ID.
        status: Optional filter for knowledge graph index status.
    Returns:
        A list of KnowledgeGraphIndexReadWithUsage instances matching the
        filters, each including usage information.
    """
    graphs = await knowledge_graph_indices_repo.list_knowledge_graph_indices(
        session,
        skip=skip,
        limit=limit,
        corpus_index_id=corpus_index_id,
        status=status,
    )
    return [await _read_with_usage(graph, session) for graph in graphs]


async def get_knowledge_graph_index_srvc(
    graph: KnowledgeGraphIndex,
    session: AsyncSession,
) -> KnowledgeGraphIndexReadWithUsage:
    """
    Get a knowledge graph index by its ID and include its usage information.
    Args:
        graph: The KnowledgeGraphIndex instance to retrieve.
        session: The database session.
    Returns:
        A KnowledgeGraphIndexReadWithUsage instance containing the graph's
        details and usage information.
    """
    return await _read_with_usage(graph, session)


async def update_knowledge_graph_index_srvc(
    graph: KnowledgeGraphIndex,
    graph_in: KnowledgeGraphIndexUpdate,
    session: AsyncSession,
) -> KnowledgeGraphIndexReadWithUsage:
    """
    Update a knowledge graph index after validating that there is no active
    build job for the graph.
    Args:
        graph: The KnowledgeGraphIndex instance to update.
        graph_in: The KnowledgeGraphIndexUpdate instance containing the
            updated graph details.
        session: The database session.
    Returns:
        A KnowledgeGraphIndexReadWithUsage instance representing the updated
        knowledge graph index.
    Raises:
        ValueError: If there is an active build job for the knowledge graph.
    """
    if (
        await knowledge_graph_build_jobs_repo.get_active_knowledge_graph_build_job(
            graph.id,
            session,
        )
        is not None
    ):
        raise ValueError("Cannot update knowledge graph during an active build")
    updated = await knowledge_graph_indices_repo.update_knowledge_graph_index(
        graph,
        graph_in,
        session,
    )
    return await _read_with_usage(updated, session)


async def delete_knowledge_graph_index_srvc(
    graph: KnowledgeGraphIndex,
    session: AsyncSession,
) -> None:
    """
    Delete a knowledge graph index after validating that there is no active
    build job for the graph.
    Args:
        graph: The KnowledgeGraphIndex instance to delete.
        session: The database session.
    Raises:
        ValueError: If there is an active build job for the knowledge graph.
    """
    if (
        await knowledge_graph_build_jobs_repo.get_active_knowledge_graph_build_job(
            graph.id,
            session,
        )
        is not None
    ):
        raise ValueError("Cannot delete knowledge graph during an active build")
    await knowledge_graph_indices_repo.delete_knowledge_graph_index(graph, session)

