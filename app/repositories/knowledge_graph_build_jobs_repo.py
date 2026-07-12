from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.knowledge_graph_build_jobs import KnowledgeGraphBuildJob
from app.repositories.helpers import commit_and_refresh, utc_now
from app.schemas.knowledge_graph_build_jobs_schemas import (
    KnowledgeGraphBuildJobCreate,
)


ACTIVE_GRAPH_BUILD_STATUSES = {"queued", "running"}


async def get_knowledge_graph_build_job_by_id(
    job_id: int,
    session: AsyncSession,
) -> KnowledgeGraphBuildJob | None:
    """
    Get a knowledge graph build job by its ID.
        Args:
            job_id: The ID of the knowledge graph build job.
            session: The database session.
        Returns:
            The KnowledgeGraphBuildJob instance if found, None otherwise.
    """
    return await session.get(KnowledgeGraphBuildJob, job_id)


async def get_active_knowledge_graph_build_job(
    graph_id: int,
    session: AsyncSession,
) -> KnowledgeGraphBuildJob | None:
    """
    Get the active knowledge graph build job for a specific graph.
        Args:
            graph_id: The ID of the knowledge graph.
            session: The database session.
        Returns:
            The active KnowledgeGraphBuildJob instance if found, None 
            otherwise.
    """
    result = await session.exec(
        select(KnowledgeGraphBuildJob)
        .where(
            KnowledgeGraphBuildJob.knowledge_graph_index_id == graph_id,
            KnowledgeGraphBuildJob.status.in_(ACTIVE_GRAPH_BUILD_STATUSES),
        )
        .order_by(KnowledgeGraphBuildJob.id.desc())
    )
    return result.first()


async def list_knowledge_graph_build_jobs(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 20,
    graph_id: int | None = None,
    status: str | None = None,
) -> list[KnowledgeGraphBuildJob]:
    """
    List knowledge graph build jobs with optional filtering by graph ID 
    and status.
        Args:
            session: The database session.
            skip: The number of records to skip for pagination.
            limit: The maximum number of records to return.
            graph_id: Optional; filter by knowledge graph ID.
            status: Optional; filter by job status.
        Returns:
            A list of KnowledgeGraphBuildJob instances matching the criteria.
    """
    statement = select(KnowledgeGraphBuildJob)
    if graph_id is not None:
        statement = statement.where(
            KnowledgeGraphBuildJob.knowledge_graph_index_id == graph_id
        )
    if status is not None:
        statement = statement.where(KnowledgeGraphBuildJob.status == status)
    result = await session.exec(
        statement.order_by(KnowledgeGraphBuildJob.id.desc()).offset(skip).limit(limit)
    )
    return list(result.all())


async def list_interrupted_knowledge_graph_build_jobs(
    session: AsyncSession,
) -> list[KnowledgeGraphBuildJob]:
    """
    Return graph build jobs left appearing active by an application 
    interruption.
        Args:
            session: The database session.
        Returns:
            A list of KnowledgeGraphBuildJob instances that appear 
            still active.
    """
    result = await session.exec(
        select(KnowledgeGraphBuildJob)
        .where(KnowledgeGraphBuildJob.status.in_(ACTIVE_GRAPH_BUILD_STATUSES))
        .order_by(KnowledgeGraphBuildJob.id.asc())
    )
    return list(result.all())


async def create_knowledge_graph_build_job(
    job_in: KnowledgeGraphBuildJobCreate,
    session: AsyncSession,
) -> KnowledgeGraphBuildJob:
    """
    Create a new knowledge graph build job.
        Args:
            job_in: The KnowledgeGraphBuildJobCreate instance containing
            the job details.
            session: The database session.
        Returns:
            The newly created KnowledgeGraphBuildJob instance.
        Raises:
            ValueError: If there is already an active build job for the
            specified knowledge graph.
    """
    if (
        await get_active_knowledge_graph_build_job(
            job_in.knowledge_graph_index_id,
            session,
        )
        is not None
    ):
        raise ValueError("Knowledge graph already has an active build job")
    job = KnowledgeGraphBuildJob(**job_in.model_dump())
    return await commit_and_refresh(session, job)


async def update_knowledge_graph_build_job(
    job: KnowledgeGraphBuildJob,
    session: AsyncSession,
    **values,
) -> KnowledgeGraphBuildJob:
    """
    Update an existing knowledge graph build job with new values.
        Args:
            job: The KnowledgeGraphBuildJob instance to update.
            session: The database session.
            **values: Key-value pairs of attributes to update on the job.
        Returns:
            The updated KnowledgeGraphBuildJob instance.
    """
    for key, value in values.items():
        setattr(job, key, value)
    return await commit_and_refresh(session, job)


async def mark_knowledge_graph_build_job_running(
    job: KnowledgeGraphBuildJob,
    session: AsyncSession,
) -> KnowledgeGraphBuildJob:
    """
    Mark a knowledge graph build job as running.
        Args:
            job: The KnowledgeGraphBuildJob instance to update.
            session: The database session.
        Returns:
            The updated KnowledgeGraphBuildJob instance.
    """
    return await update_knowledge_graph_build_job(
        job,
        session,
        status="running",
        stage="extracting",
        started_at=utc_now(),
        cancel_requested=False,
    )


async def mark_knowledge_graph_build_job_completed(
    job: KnowledgeGraphBuildJob,
    session: AsyncSession,
) -> KnowledgeGraphBuildJob:
    """
    Mark a knowledge graph build job as completed.
        Args:
            job: The KnowledgeGraphBuildJob instance to update.
            session: The database session.
        Returns:
            The updated KnowledgeGraphBuildJob instance.
    """
    return await update_knowledge_graph_build_job(
        job,
        session,
        status="completed",
        stage="finished",
        completed_at=utc_now(),
        cancel_requested=False,
    )


async def mark_knowledge_graph_build_job_failed(
    job: KnowledgeGraphBuildJob,
    detail: str,
    session: AsyncSession,
) -> KnowledgeGraphBuildJob:
    """
    Mark a knowledge graph build job as failed with a failure detail.
        Args:
            job: The KnowledgeGraphBuildJob instance to update.
            detail: A string describing the reason for failure.
            session: The database session.
        Returns:
            The updated KnowledgeGraphBuildJob instance.
    """
    return await update_knowledge_graph_build_job(
        job,
        session,
        status="failed",
        stage="finished",
        completed_at=utc_now(),
        failure_detail=detail,
        cancel_requested=False,
    )


async def mark_knowledge_graph_build_job_cancelled(
    job: KnowledgeGraphBuildJob,
    session: AsyncSession,
) -> KnowledgeGraphBuildJob:
    """
    Mark a knowledge graph build job as cancelled.
        Args:
            job: The KnowledgeGraphBuildJob instance to update.
            session: The database session.
        Returns:
            The updated KnowledgeGraphBuildJob instance.
    """
    return await update_knowledge_graph_build_job(
        job,
        session,
        status="cancelled",
        stage="finished",
        completed_at=utc_now(),
        failure_detail="Knowledge graph build cancelled",
        cancel_requested=False,
    )
