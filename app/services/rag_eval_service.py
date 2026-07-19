"""Service boundary for persistent RAG evaluation configurations and runs."""

from __future__ import annotations
from collections.abc import Callable
from typing import Any
from sqlmodel.ext.asyncio.session import AsyncSession

# local imports
from app.airag.evaluation.rag_eval_helpers import create_eval_corpus
from app.models.rag_eval import RagEvalConfiguration, RagEvalRun
from app.models.users import User
from app.repositories import rag_eval_repo
from app.schemas.rag_eval_schemas import (
    RagEvalConfigurationCreate,
    RagEvalConfigurationCreateRequest,
    RagEvalConfigurationRead,
    RagEvalConfigurationUpdate,
    RagEvalConfigurationUpdateRequest,
    RagEvalQueryResultRead,
    RagEvalRunDetailRead,
    RagEvalRunRead,
)
from app.services.rag_eval_coordinator import (
    RagEvalCoordinator,
    rag_eval_coordinator,
)


def _configuration_read(
    configuration: RagEvalConfiguration,
) -> RagEvalConfigurationRead:
    """
    Convert a RagEvalConfiguration model instance to a RagEvalConfigurationRead schema.
    Args:
        configuration (RagEvalConfiguration): The RAG evaluation configuration model instance.
    Returns:
        RagEvalConfigurationRead: The RAG evaluation configuration read schema."""
    return RagEvalConfigurationRead.model_validate(
        configuration,
        from_attributes=True,
    )

def _run_read(run: RagEvalRun) -> RagEvalRunRead:
    """
    Convert a RagEvalRun model instance to a RagEvalRunRead schema.
    Args:
        run (RagEvalRun): The RAG evaluation run model instance.
    Returns:
        RagEvalRunRead: The RAG evaluation run read schema.
    """
    return RagEvalRunRead.model_validate(run, from_attributes=True)


async def create_rag_eval_configuration_srvc(
    data: RagEvalConfigurationCreateRequest,
    session: AsyncSession,
    current_user: User,
) -> RagEvalConfigurationRead:
    """
    Create a new RAG evaluation configuration in the database.
    Args:
        data (RagEvalConfigurationCreateRequest): The configuration data 
            to create.
        session (AsyncSession): The database session.
        current_user (User): The user creating the configuration.
    Returns:
        RagEvalConfigurationRead: The newly created RAG evaluation 
        configuration.
    Raises:
        ValueError: If the RAG configuration is not found.
    """
    configuration = await rag_eval_repo.create_rag_eval_configuration(
        RagEvalConfigurationCreate(
            **data.model_dump(mode="python"),
            created_by_user_id=current_user.id,
        ),
        session,
    )
    return _configuration_read(configuration)


async def list_rag_eval_configurations_srvc(
    session: AsyncSession,
    *,
    skip: int,
    limit: int,
) -> list[RagEvalConfigurationRead]:
    """
    List all RAG evaluation configurations in the database.
    Args:
        session (AsyncSession): The database session.
        skip (int): The number of configurations to skip for pagination.
        limit (int): The maximum number of configurations to return.
    Returns:
        list[RagEvalConfigurationRead]: A list of RAG evaluation 
        configurations.
    """
    configurations = await rag_eval_repo.list_rag_eval_configurations(
        session,
        skip=skip,
        limit=limit,
    )
    return [_configuration_read(item) for item in configurations]


async def get_rag_eval_configuration_srvc(
    configuration_id: int,
    session: AsyncSession,
) -> RagEvalConfigurationRead:
    """
    Get a RAG evaluation configuration by its ID.
    Args:
        configuration_id (int): The ID of the configuration to retrieve.
        session (AsyncSession): The database session.
    Returns:
        RagEvalConfigurationRead: The RAG evaluation configuration with 
        the specified ID.
    Raises:
        ValueError: If the configuration is not found.
    """
    configuration = await rag_eval_repo.get_rag_eval_configuration_by_id(
        configuration_id,
        session,
    )
    if configuration is None:
        raise ValueError("RAG evaluation configuration not found")
    return _configuration_read(configuration)


async def update_rag_eval_configuration_srvc(
    configuration_id: int,
    data: RagEvalConfigurationUpdateRequest,
    session: AsyncSession,
    current_user: User,
) -> RagEvalConfigurationRead:
    """
    Service function to update a RAG evaluation configuration in the database.
    Args:
        configuration_id (int): The ID of the configuration to update.
        data (RagEvalConfigurationUpdateRequest): The updated configuration
            data.
        session (AsyncSession): The database session.
        current_user (User): The user performing the update.
    Returns:
        RagEvalConfigurationRead: The updated RAG evaluation configuration.
    Raises:
        ValueError: If the configuration is not found.
    """
    # Get the existing configuration from the database
    configuration = await rag_eval_repo.get_rag_eval_configuration_by_id(
        configuration_id,
        session,
    )
    if configuration is None:
        raise ValueError("RAG evaluation configuration not found")
    updated = await rag_eval_repo.update_rag_eval_configuration(
        configuration,
        RagEvalConfigurationUpdate(
            **data.model_dump(exclude_unset=True, mode="python"),
            last_edit_by_user_id=current_user.id,
        ),
        session,
    )
    return _configuration_read(updated)


async def delete_rag_eval_configuration_srvc(
    configuration_id: int,
    session: AsyncSession,
) -> None:
    """
    Delete a RAG evaluation configuration by its ID.
    Args:
        configuration_id (int): The ID of the configuration to delete.
        session (AsyncSession): The database session.
    Returns:
        None
    Raises:
        ValueError: If the configuration is not found.
    """
    configuration = await rag_eval_repo.get_rag_eval_configuration_by_id(
        configuration_id,
        session,
    )
    if configuration is None:
        raise ValueError("RAG evaluation configuration not found")
    await rag_eval_repo.delete_rag_eval_configuration(configuration, session)


async def enqueue_rag_eval_run_srvc(
    configuration_id: int,
    session: AsyncSession,
    *,
    coordinator: RagEvalCoordinator = rag_eval_coordinator,
    corpus_factory: Callable[[], Any] = create_eval_corpus,
) -> RagEvalRunRead:
    """
    Queue a new RAG evaluation run for the given configuration.
    The run will be processed asynchronously by the RAG evaluation coordinator.
    Args:
        configuration_id (int): The ID of the RAG evaluation configuration.
        session (AsyncSession): The database session.
        coordinator (RagEvalCoordinator, optional): The RAG evaluation coordinator.
        corpus_factory (Callable[[], Any], optional): A factory function to create the evaluation corpus.
    Returns:
        RagEvalRunRead: The details of the enqueued RAG evaluation run.
    Raises:
        ValueError: If the configuration is not found.
    """
    configuration = await rag_eval_repo.get_rag_eval_configuration_by_id(
        configuration_id,
        session,
    )
    if configuration is None:
        raise ValueError("RAG evaluation configuration not found")
    corpus = corpus_factory()
    run = await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version=corpus.suite_version,
        suite_content_hash=corpus.suite_content_hash,
        total_examples=len(corpus.examples),
        session=session,
    )
    coordinator.wake()
    return _run_read(run)


async def list_rag_eval_runs_srvc(
    session: AsyncSession,
    *,
    skip: int,
    limit: int,
    configuration_id: int | None = None,
    status: str | None = None,
) -> list[RagEvalRunRead]:
    """
    List RAG evaluation runs, optionally filtered by configuration ID 
    and status.
    Args:
        session (AsyncSession): The database session.
        skip (int): The number of runs to skip for pagination.
        limit (int): The maximum number of runs to return.
        configuration_id (int | None, optional): Filter runs by configuration ID.
        status (str | None, optional): Filter runs by status.
    Returns:
        list[RagEvalRunRead]: A list of RAG evaluation runs.
    """
    runs = await rag_eval_repo.list_rag_eval_runs(
        session,
        skip=skip,
        limit=limit,
        configuration_id=configuration_id,
        status=status,
    )
    return [_run_read(item) for item in runs]


async def get_rag_eval_run_srvc(
    run_id: int,
    session: AsyncSession,
) -> RagEvalRunDetailRead:
    """
    Get a RAG evaluation run results by its ID.
    Args:
        run_id (int): The ID of the RAG evaluation run.
        session (AsyncSession): The database session.
    Returns:
        RagEvalRunDetailRead: The details of the RAG evaluation run.
    Raises:
        ValueError: If the RAG evaluation run is not found.
    """
    run = await rag_eval_repo.get_rag_eval_run_by_id(run_id, session)
    if run is None:
        raise ValueError("RAG evaluation run not found")
    rows = await rag_eval_repo.list_rag_eval_query_results(run_id, session)
    return RagEvalRunDetailRead(
        **_run_read(run).model_dump(),
        query_results=[
            RagEvalQueryResultRead.model_validate(row, from_attributes=True)
            for row in rows
        ],
    )


async def cancel_rag_eval_run_srvc(
    run_id: int,
    session: AsyncSession,
    *,
    coordinator: RagEvalCoordinator = rag_eval_coordinator,
) -> RagEvalRunRead:
    """
    Cancel a RAG evaluation run service function.
    Args:
        run_id (int): The ID of the RAG evaluation run.
        session (AsyncSession): The database session.
        coordinator (RagEvalCoordinator, optional): The RAG evaluation coordinator.
    Returns:
        RagEvalRunRead: The details of the cancelled RAG evaluation run.
    Raises:
        ValueError: If the RAG evaluation run is not found.
    """
    # Get the run from the database
    run = await rag_eval_repo.get_rag_eval_run_by_id(run_id, session)
    if run is None:
        raise ValueError("RAG evaluation run not found")
    cancelled = await rag_eval_repo.request_rag_eval_run_cancel(run, session)
    coordinator.wake()
    return _run_read(cancelled)


async def startup_rag_eval_coordinator_srvc(
    coordinator: RagEvalCoordinator = rag_eval_coordinator,
) -> None:
    """
    Start the RAG evaluation coordinator.
    Args:
        coordinator (RagEvalCoordinator, optional): The RAG evaluation coordinator.
    Returns:
        None
    """
    await coordinator.start()


async def shutdown_rag_eval_coordinator_srvc(
    coordinator: RagEvalCoordinator = rag_eval_coordinator,
) -> None:
    """
    Stop the RAG evaluation coordinator.
    Args:
        coordinator (RagEvalCoordinator, optional): The RAG evaluation coordinator.
    Returns:
        None
    """
    await coordinator.stop()
