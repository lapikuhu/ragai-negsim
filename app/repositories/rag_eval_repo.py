from typing import Any, Iterable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.rag_eval import (
    RagEvalConfiguration,
    RagEvalQueryResult,
    RagEvalRun,
)
from app.repositories.helpers import commit_and_refresh, commit_delete, utc_now
from app.schemas.rag_eval_schemas import (
    RagEvalConfigurationCreate,
    RagEvalConfigurationCreateRequest,
    RagEvalConfigurationUpdate,
    RagEvalQueryResultCreate,
    apply_rag_eval_configuration_patch,
    dump_rag_eval_configuration_snapshot,
)


TERMINAL_RAG_EVAL_RUN_STATUSES = {"completed", "failed", "cancelled"}
RAG_EVAL_RUN_STAGES = {
    "queued",
    "preparing",
    "chunking",
    "building_index",
    "building_graph",
    "evaluating",
    "scoring",
    "cleaning_up",
    "persisting",
    "finished",
    "cleanup_pending",
}
_RAG_EVAL_RUN_TRANSITIONS = {
    "queued": {"running", "cancelled", "failed"},
    "running": {"completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


def _configuration_payload(
    configuration: RagEvalConfiguration,
) -> RagEvalConfigurationCreateRequest:
    return RagEvalConfigurationCreateRequest.model_validate(
        {
            "name": configuration.name,
            "chunking": configuration.chunking,
            "rag": configuration.rag,
            "metrics": configuration.metrics,
        }
    )


async def get_rag_eval_configuration_by_id(
    configuration_id: int,
    session: AsyncSession,
) -> RagEvalConfiguration | None:
    return await session.get(RagEvalConfiguration, configuration_id)


async def get_rag_eval_configuration_by_name(
    name: str,
    session: AsyncSession,
) -> RagEvalConfiguration | None:
    result = await session.exec(
        select(RagEvalConfiguration).where(RagEvalConfiguration.name == name)
    )
    return result.first()


async def ensure_rag_eval_configuration_name_available(
    name: str,
    session: AsyncSession,
    exclude_configuration_id: int | None = None,
) -> None:
    existing = await get_rag_eval_configuration_by_name(name, session)
    if existing is not None and existing.id != exclude_configuration_id:
        raise ValueError("RAG evaluation configuration name already exists")


async def list_rag_eval_configurations(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 20,
) -> list[RagEvalConfiguration]:
    result = await session.exec(
        select(RagEvalConfiguration)
        .order_by(RagEvalConfiguration.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.all())


async def create_rag_eval_configuration(
    configuration_in: RagEvalConfigurationCreate,
    session: AsyncSession,
) -> RagEvalConfiguration:
    await ensure_rag_eval_configuration_name_available(
        configuration_in.name,
        session,
    )
    normalized = RagEvalConfigurationCreate.model_validate(configuration_in)
    configuration = RagEvalConfiguration(
        name=normalized.name,
        chunking=normalized.chunking.model_dump(mode="json"),
        rag=normalized.rag.model_dump(mode="json"),
        metrics=normalized.metrics.model_dump(mode="json"),
        created_by_user_id=normalized.created_by_user_id,
    )
    return await commit_and_refresh(session, configuration)


async def update_rag_eval_configuration(
    configuration: RagEvalConfiguration,
    configuration_in: RagEvalConfigurationUpdate,
    session: AsyncSession,
) -> RagEvalConfiguration:
    if configuration.id is None:
        raise ValueError("RAG evaluation configuration must be persisted")
    normalized = apply_rag_eval_configuration_patch(
        _configuration_payload(configuration),
        configuration_in,
    )
    await ensure_rag_eval_configuration_name_available(
        normalized.name,
        session,
        configuration.id,
    )
    configuration.name = normalized.name
    configuration.chunking = normalized.chunking.model_dump(mode="json")
    configuration.rag = normalized.rag.model_dump(mode="json")
    configuration.metrics = normalized.metrics.model_dump(mode="json")
    if "last_edit_by_user_id" in configuration_in.model_fields_set:
        configuration.last_edit_by_user_id = configuration_in.last_edit_by_user_id
    configuration.last_updated = utc_now()
    return await commit_and_refresh(session, configuration)


async def rag_eval_configuration_has_runs(
    configuration_id: int,
    session: AsyncSession,
) -> bool:
    result = await session.exec(
        select(RagEvalRun.id)
        .where(RagEvalRun.configuration_id == configuration_id)
        .limit(1)
    )
    return result.first() is not None


async def delete_rag_eval_configuration(
    configuration: RagEvalConfiguration,
    session: AsyncSession,
) -> None:
    if configuration.id is None:
        raise ValueError("RAG evaluation configuration must be persisted")
    if await rag_eval_configuration_has_runs(configuration.id, session):
        raise ValueError(
            "Cannot delete RAG evaluation configuration referenced by evaluation runs"
        )
    await commit_delete(session, configuration)


async def enqueue_rag_eval_run(
    configuration: RagEvalConfiguration,
    *,
    suite_version: str,
    suite_content_hash: str,
    total_examples: int,
    session: AsyncSession,
) -> RagEvalRun:
    if configuration.id is None:
        raise ValueError("RAG evaluation configuration must be persisted")
    if total_examples < 0:
        raise ValueError("total_examples must be non-negative")
    snapshot = dump_rag_eval_configuration_snapshot(
        _configuration_payload(configuration)
    )
    run = RagEvalRun(
        configuration_id=configuration.id,
        configuration_snapshot=snapshot,
        suite_version=suite_version,
        suite_content_hash=suite_content_hash,
        total_examples=total_examples,
    )
    return await commit_and_refresh(session, run)


async def get_rag_eval_run_by_id(
    run_id: int,
    session: AsyncSession,
) -> RagEvalRun | None:
    return await session.get(RagEvalRun, run_id)


async def list_rag_eval_runs(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 20,
    configuration_id: int | None = None,
    status: str | None = None,
) -> list[RagEvalRun]:
    statement = select(RagEvalRun)
    if configuration_id is not None:
        statement = statement.where(
            RagEvalRun.configuration_id == configuration_id
        )
    if status is not None:
        statement = statement.where(RagEvalRun.status == status)
    result = await session.exec(
        statement.order_by(RagEvalRun.queued_at.desc(), RagEvalRun.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.all())


def _next_queued_rag_eval_run_statement():
    return (
        select(RagEvalRun)
        .where(RagEvalRun.status == "queued")
        .order_by(RagEvalRun.queued_at.asc(), RagEvalRun.id.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )


async def claim_next_rag_eval_run(
    session: AsyncSession,
) -> RagEvalRun | None:
    running = await session.exec(
        select(RagEvalRun.id).where(RagEvalRun.status == "running").limit(1)
    )
    if running.first() is not None:
        return None

    result = await session.exec(_next_queued_rag_eval_run_statement())
    run = result.first()
    if run is None:
        return None
    run.status = "running"
    run.stage = "preparing"
    run.started_at = utc_now()
    run.cancel_requested = False
    session.add(run)
    try:
        await session.commit()
        await session.refresh(run)
        return run
    except IntegrityError:
        # A concurrent claimant won the global-running partial unique index.
        await session.rollback()
        return None


def _validate_rag_eval_run_transition(
    current_status: str,
    next_status: str,
) -> None:
    if next_status not in _RAG_EVAL_RUN_TRANSITIONS.get(current_status, set()):
        raise ValueError(
            "Invalid RAG evaluation run status transition: "
            f"{current_status!r} -> {next_status!r}"
        )


async def transition_rag_eval_run(
    run: RagEvalRun,
    next_status: str,
    *,
    session: AsyncSession,
    stage: str | None = None,
    **values: Any,
) -> RagEvalRun:
    if next_status != run.status:
        _validate_rag_eval_run_transition(run.status, next_status)
    if stage is not None and stage not in RAG_EVAL_RUN_STAGES:
        raise ValueError(f"Invalid RAG evaluation run stage: {stage!r}")
    run.status = next_status
    if stage is not None:
        run.stage = stage
    for key, value in values.items():
        if not hasattr(run, key):
            raise ValueError(f"Unknown RAG evaluation run field: {key}")
        setattr(run, key, value)
    if next_status in TERMINAL_RAG_EVAL_RUN_STATUSES and run.completed_at is None:
        run.completed_at = utc_now()
    session.add(run)
    try:
        await session.commit()
        await session.refresh(run)
        return run
    except Exception:
        await session.rollback()
        raise


async def update_rag_eval_run_progress(
    run: RagEvalRun,
    *,
    stage: str,
    progress: float,
    completed_examples: int,
    total_examples: int,
    session: AsyncSession,
) -> RagEvalRun:
    if run.status != "running":
        raise ValueError("Progress can only be updated for a running evaluation")
    if stage not in RAG_EVAL_RUN_STAGES:
        raise ValueError(f"Invalid RAG evaluation run stage: {stage!r}")
    if not 0 <= progress <= 100:
        raise ValueError("progress must be between 0 and 100")
    if not 0 <= completed_examples <= total_examples:
        raise ValueError("completed_examples must be between 0 and total_examples")
    run.stage = stage
    run.progress = progress
    run.completed_examples = completed_examples
    run.total_examples = total_examples
    return await commit_and_refresh(session, run)


async def request_rag_eval_run_cancel(
    run: RagEvalRun,
    session: AsyncSession,
) -> RagEvalRun:
    if run.status in TERMINAL_RAG_EVAL_RUN_STATUSES:
        raise ValueError("Cannot cancel a finished RAG evaluation run")
    now = utc_now()
    if run.status == "queued":
        return await transition_rag_eval_run(
            run,
            "cancelled",
            stage="finished",
            cancellation_requested_at=now,
            cancel_requested=False,
            session=session,
        )
    run.cancel_requested = True
    run.cancellation_requested_at = now
    return await commit_and_refresh(session, run)


async def list_interrupted_rag_eval_runs(
    session: AsyncSession,
) -> list[RagEvalRun]:
    result = await session.exec(
        select(RagEvalRun)
        .where(
            or_(
                RagEvalRun.status == "running",
                RagEvalRun.stage == "cleanup_pending",
            )
        )
        .order_by(RagEvalRun.started_at.asc(), RagEvalRun.id.asc())
    )
    return list(result.all())


async def finalize_rag_eval_run_success(
    run: RagEvalRun,
    results: Iterable[RagEvalQueryResultCreate | dict[str, Any]],
    *,
    overall_metrics: dict[str, Any],
    category_metrics: dict[str, Any],
    resolved_pipeline_snapshot: dict[str, Any],
    session: AsyncSession,
) -> RagEvalRun:
    if run.status != "running":
        raise ValueError("Only a running evaluation can be finalized")
    buffered = [
        (
            item
            if isinstance(item, RagEvalQueryResultCreate)
            else RagEvalQueryResultCreate.model_validate(item)
        )
        for item in results
    ]
    if run.id is None:
        raise ValueError("RAG evaluation run must be persisted")

    rows = [
        RagEvalQueryResult(
            run_id=run.id,
            **item.model_dump(mode="json"),
        )
        for item in buffered
    ]
    try:
        session.add_all(rows)
        await session.flush()
        run.status = "completed"
        run.stage = "finished"
        run.progress = 100.0
        run.completed_examples = run.total_examples
        run.completed_at = utc_now()
        run.cancel_requested = False
        run.resolved_pipeline_snapshot = dict(resolved_pipeline_snapshot)
        run.overall_metrics = dict(overall_metrics)
        run.category_metrics = dict(category_metrics)
        session.add(run)
        await session.flush()
        await session.commit()
        await session.refresh(run)
        return run
    except Exception:
        await session.rollback()
        raise


async def list_rag_eval_query_results(
    run_id: int,
    session: AsyncSession,
) -> list[RagEvalQueryResult]:
    result = await session.exec(
        select(RagEvalQueryResult)
        .where(RagEvalQueryResult.run_id == run_id)
        .order_by(RagEvalQueryResult.id.asc())
    )
    return list(result.all())


# Temporary compatibility names for the legacy service layer.
get_rag_eval_pair_profile_by_id = get_rag_eval_configuration_by_id
get_rag_eval_pair_profile_by_name = get_rag_eval_configuration_by_name
ensure_rag_eval_pair_profile_name_available = (
    ensure_rag_eval_configuration_name_available
)
list_rag_eval_pair_profiles = list_rag_eval_configurations
create_rag_eval_pair_profile = create_rag_eval_configuration
rag_eval_pair_profile_has_runs = rag_eval_configuration_has_runs
update_rag_eval_pair_profile = update_rag_eval_configuration
delete_rag_eval_pair_profile = delete_rag_eval_configuration


async def get_active_rag_eval_run(
    configuration_id: int,
    session: AsyncSession,
) -> RagEvalRun | None:
    result = await session.exec(
        select(RagEvalRun)
        .where(
            RagEvalRun.configuration_id == configuration_id,
            RagEvalRun.status.in_({"queued", "running"}),
        )
        .order_by(RagEvalRun.id.desc())
    )
    return result.first()


async def update_rag_eval_run(
    run: RagEvalRun,
    session: AsyncSession,
    **values: Any,
) -> RagEvalRun:
    next_status = values.pop("status", run.status)
    stage = values.pop("stage", None)
    return await transition_rag_eval_run(
        run,
        next_status,
        stage=stage,
        session=session,
        **values,
    )


async def mark_rag_eval_run_running(
    run: RagEvalRun,
    session: AsyncSession,
) -> RagEvalRun:
    return await transition_rag_eval_run(
        run,
        "running",
        stage="preparing",
        started_at=utc_now(),
        cancel_requested=False,
        session=session,
    )


async def mark_rag_eval_run_failed(
    run: RagEvalRun,
    detail: str,
    session: AsyncSession,
) -> RagEvalRun:
    return await transition_rag_eval_run(
        run,
        "failed",
        stage="finished",
        failure_code="evaluation_failed",
        failure_message=detail,
        cancel_requested=False,
        session=session,
    )


async def mark_rag_eval_run_cancelled(
    run: RagEvalRun,
    session: AsyncSession,
) -> RagEvalRun:
    return await transition_rag_eval_run(
        run,
        "cancelled",
        stage="finished",
        cancel_requested=False,
        session=session,
    )


async def create_rag_eval_run(*_args: Any, **_kwargs: Any) -> RagEvalRun:
    """Legacy service shim; new callers must use enqueue_rag_eval_run."""
    raise RuntimeError("Use enqueue_rag_eval_run with a complete configuration")


async def create_rag_eval_query_result(
    *_args: Any,
    **_kwargs: Any,
) -> RagEvalQueryResult:
    """Legacy service shim; successful results must use atomic finalization."""
    raise RuntimeError("Use finalize_rag_eval_run_success for atomic persistence")


async def mark_rag_eval_run_completed(
    *_args: Any,
    **_kwargs: Any,
) -> RagEvalRun:
    """Legacy service shim; successful results must use atomic finalization."""
    raise RuntimeError("Use finalize_rag_eval_run_success for atomic persistence")
