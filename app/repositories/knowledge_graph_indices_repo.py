from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.knowledge_graph_indices import KnowledgeGraphIndex
from app.models.rag_profiles import RagProfile
from app.models.simulations import Simulation
from app.repositories.helpers import commit_and_refresh, commit_delete, utc_now
from app.schemas.knowledge_graph_indices_schemas import (
    KnowledgeGraphIndexCreate,
    KnowledgeGraphIndexUpdate,
)


async def get_knowledge_graph_index_by_id(
    graph_id: int,
    session: AsyncSession,
) -> KnowledgeGraphIndex | None:
    """
    Get a knowledge graph index by its ID.
        Args:
            graph_id: The ID of the knowledge graph index.
            session: The database session.
        Returns:
            The KnowledgeGraphIndex instance if found, else None.
    """
    return await session.get(KnowledgeGraphIndex, graph_id)


async def get_knowledge_graph_index_by_name(
    name: str,
    session: AsyncSession,
) -> KnowledgeGraphIndex | None:
    """
    Get a knowledge graph index by its name.
        Args:
            name: The name of the knowledge graph index.
            session: The database session.
        Returns:
            The KnowledgeGraphIndex instance if found, else None.
    """
    result = await session.exec(
        select(KnowledgeGraphIndex).where(KnowledgeGraphIndex.name == name)
    )
    return result.first()


async def list_knowledge_graph_indices(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 20,
    corpus_index_id: int | None = None,
    status: str | None = None,
) -> list[KnowledgeGraphIndex]:
    """
    List knowledge graph indices with optional filtering by corpus index 
    ID and status.
        Args:
            session: The database session.
            skip: The number of records to skip for pagination.
            limit: The maximum number of records to return.
            corpus_index_id: Optional filter for corpus index ID.
            status: Optional filter for knowledge graph index status.
        Returns:
            A list of KnowledgeGraphIndex instances matching the filters.
    """
    statement = select(KnowledgeGraphIndex)
    if corpus_index_id is not None:
        statement = statement.where(
            KnowledgeGraphIndex.corpus_index_id == corpus_index_id
        )
    if status is not None:
        statement = statement.where(KnowledgeGraphIndex.status == status)
    result = await session.exec(
        statement.order_by(KnowledgeGraphIndex.id.desc()).offset(skip).limit(limit)
    )
    return list(result.all())


async def create_knowledge_graph_index(
    graph_in: KnowledgeGraphIndexCreate,
    session: AsyncSession,
) -> KnowledgeGraphIndex:
    """
    Create a new knowledge graph index.
        Args:
            graph_in: The KnowledgeGraphIndexCreate instance containing
            the graph details.
            session: The database session.
        Returns:
            The newly created KnowledgeGraphIndex instance.
        Raises:
            ValueError: If a knowledge graph with the same name already exists.
    """
    if await get_knowledge_graph_index_by_name(graph_in.name, session) is not None:
        raise ValueError("Knowledge graph name already exists")
    graph = KnowledgeGraphIndex(**graph_in.model_dump())
    return await commit_and_refresh(session, graph)


async def ensure_knowledge_graph_mutable(
    graph: KnowledgeGraphIndex,
    session: AsyncSession,
) -> None:
    """
    Ensure that a knowledge graph index is mutable (not locked) before performing
    operations that modify it.
        Args:
            graph: The KnowledgeGraphIndex instance to check.
            session: The database session.
        Returns:
            None
        Raises:
            ValueError: If the knowledge graph is locked or not persisted.
    """
    if graph.id is None:
        raise ValueError("Knowledge graph must be persisted before this operation")
    if graph.locked_at is not None:
        raise ValueError("Cannot modify knowledge graph used in a simulation")


async def update_knowledge_graph_index(
    graph: KnowledgeGraphIndex,
    graph_in: KnowledgeGraphIndexUpdate,
    session: AsyncSession,
) -> KnowledgeGraphIndex:
    """
    Update an existing knowledge graph index with new values.
        Args:
            graph: The KnowledgeGraphIndex instance to update.
            graph_in: The KnowledgeGraphIndexUpdate instance containing
            the new values.
            session: The database session.
        Returns:
            The updated KnowledgeGraphIndex instance.
        Raises:
            ValueError: If the knowledge graph is locked or if the new name
            already exists for another graph.
    """
    await ensure_knowledge_graph_mutable(graph, session)
    values = graph_in.model_dump(exclude_unset=True)
    if "name" in values and values["name"] != graph.name:
        existing = await get_knowledge_graph_index_by_name(values["name"], session)
        if existing is not None:
            raise ValueError("Knowledge graph name already exists")
    for key, value in values.items():
        setattr(graph, key, value)
    graph.last_updated = utc_now()
    return await commit_and_refresh(session, graph)


async def get_knowledge_graph_usage(
    graph_id: int,
    session: AsyncSession,
) -> tuple[list[int], list[int]]:
    """
    Get the usage of a knowledge graph index, including the IDs of RAG profiles
    and simulations that reference it.
        Args:
            graph_id: The ID of the knowledge graph index.
            session: The database session.
        Returns:
            A tuple containing two lists:
            - The first list contains the IDs of RAG profiles that 
            reference the knowledge graph.
            - The second list contains the IDs of simulations that 
            reference the RAG profiles.
    """
    profiles_result = await session.exec(
        select(RagProfile.id).where(RagProfile.knowledge_graph_index_id == graph_id)
    )
    profile_ids = [value for value in profiles_result.all() if value is not None]
    if not profile_ids:
        return [], []
    simulations_result = await session.exec(
        select(Simulation.id).where(Simulation.rag_profile_id.in_(profile_ids))
    )
    simulation_ids = [
        value for value in simulations_result.all() if value is not None
    ]
    return profile_ids, simulation_ids


async def lock_knowledge_graph(
    graph: KnowledgeGraphIndex,
    session: AsyncSession,
    *,
    locked_at: datetime | None = None,
) -> KnowledgeGraphIndex:
    """
    Lock a knowledge graph index to prevent modifications.
        Args:
            graph: The KnowledgeGraphIndex instance to lock.
            session: The database session.
            locked_at: The datetime to set as the lock time. If None, the 
                current UTC time is used.
        Returns:
            The locked KnowledgeGraphIndex instance.
    """
    if graph.locked_at is not None:
        return graph
    graph.locked_at = locked_at or utc_now()
    graph.last_updated = graph.locked_at
    return await commit_and_refresh(session, graph)


async def delete_knowledge_graph_index(
    graph: KnowledgeGraphIndex,
    session: AsyncSession,
) -> None:
    """
    Delete a knowledge graph index.
        Args:
            graph: The KnowledgeGraphIndex instance to delete.
            session: The database session.
        Raises:
            ValueError: If the knowledge graph is locked or if it is 
            referenced by RAG profiles.
    """
    await ensure_knowledge_graph_mutable(graph, session)
    profile_ids, _ = await get_knowledge_graph_usage(graph.id, session)
    if profile_ids:
        raise ValueError("Cannot delete knowledge graph referenced by RAG profiles")
    await commit_delete(session, graph)

