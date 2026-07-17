"""Service boundary for persistent RAG evaluation configurations and runs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

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
    return RagEvalConfigurationRead.model_validate(
        configuration,
        from_attributes=True,
    )


def _run_read(run: RagEvalRun) -> RagEvalRunRead:
    return RagEvalRunRead.model_validate(run, from_attributes=True)


async def create_rag_eval_configuration_srvc(
    data: RagEvalConfigurationCreateRequest,
    session: AsyncSession,
    current_user: User,
) -> RagEvalConfigurationRead:
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
    pair_profile_id: int | None = None,
) -> list[RagEvalRunRead]:
    # ``pair_profile_id`` is a temporary route-import bridge until Task 8
    # replaces the legacy route. It maps to the target configuration ID.
    if configuration_id is None:
        configuration_id = pair_profile_id
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
    run = await rag_eval_repo.get_rag_eval_run_by_id(run_id, session)
    if run is None:
        raise ValueError("RAG evaluation run not found")
    cancelled = await rag_eval_repo.request_rag_eval_run_cancel(run, session)
    coordinator.wake()
    return _run_read(cancelled)


async def startup_rag_eval_coordinator_srvc(
    coordinator: RagEvalCoordinator = rag_eval_coordinator,
) -> None:
    await coordinator.start()


async def shutdown_rag_eval_coordinator_srvc(
    coordinator: RagEvalCoordinator = rag_eval_coordinator,
) -> None:
    await coordinator.stop()


# Temporary import bridges for the legacy route module. Task 8 replaces that route
# with the configuration/run API and removes these names.
create_rag_eval_pair_profile_srvc = create_rag_eval_configuration_srvc
list_rag_eval_pair_profiles_srvc = list_rag_eval_configurations_srvc
get_rag_eval_pair_profile_srvc = get_rag_eval_configuration_srvc
update_rag_eval_pair_profile_srvc = update_rag_eval_configuration_srvc
delete_rag_eval_pair_profile_srvc = delete_rag_eval_configuration_srvc


async def start_rag_eval_run_srvc(
    configuration_id: int,
    _legacy_request: Any,
    session: AsyncSession,
) -> RagEvalRunRead:
    return await enqueue_rag_eval_run_srvc(configuration_id, session)


async def fail_interrupted_rag_eval_runs_srvc() -> None:
    """Compatibility startup hook; coordinator startup owns recovery now."""
    await startup_rag_eval_coordinator_srvc()
