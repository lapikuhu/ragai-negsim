from typing import Any, Iterable

from sqlalchemy import update
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
_MUTABLE_RAG_EVAL_RUN_FIELDS = {
    "stage",
    "progress",
    "completed_examples",
    "total_examples",
    "cancel_requested",
    "cancellation_requested_at",
    "failure_code",
    "failure_message",
    "resolved_pipeline_snapshot",
}


class RagEvalFinalizationCancelled(Exception):
    """Raised when cancellation wins the locked success-finalization race."""


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
    if run.id is None:
        raise ValueError("RAG evaluation run must be persisted")
    expected_status = run.status
    if expected_status == "queued" and next_status == "running":
        raise ValueError(
            "Queued RAG evaluation runs may only be started by "
            "claim_next_rag_eval_run"
        )
    if next_status != expected_status:
        _validate_rag_eval_run_transition(expected_status, next_status)
    if stage is not None and stage not in RAG_EVAL_RUN_STAGES:
        raise ValueError(f"Invalid RAG evaluation run stage: {stage!r}")
    invalid_fields = set(values) - _MUTABLE_RAG_EVAL_RUN_FIELDS - {
        "started_at",
        "completed_at",
    }
    if invalid_fields:
        fields = ", ".join(sorted(invalid_fields))
        raise ValueError(f"RAG evaluation run fields are not mutable: {fields}")

    updates = dict(values)
    updates["status"] = next_status
    if stage is not None:
        updates["stage"] = stage
    if next_status in TERMINAL_RAG_EVAL_RUN_STATUSES:
        updates.setdefault("completed_at", utc_now())
    try:
        with session.no_autoflush:
            result = await session.exec(
                update(RagEvalRun)
                .where(
                    RagEvalRun.id == run.id,
                    RagEvalRun.status == expected_status,
                )
                .values(**updates)
                .execution_options(synchronize_session=False)
            )
        if result.rowcount != 1:
            await session.rollback()
            await session.refresh(run)
            raise ValueError("RAG evaluation run changed concurrently")
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
    return await transition_rag_eval_run(
        run,
        run.status,
        stage=stage,
        progress=progress,
        completed_examples=completed_examples,
        total_examples=total_examples,
        session=session,
    )


async def request_rag_eval_run_cancel(
    run: RagEvalRun,
    session: AsyncSession,
) -> RagEvalRun:
    if run.id is None:
        raise ValueError("RAG evaluation run must be persisted")
    now = utc_now()
    try:
        with session.no_autoflush:
            queued_result = await session.exec(
                update(RagEvalRun)
                .where(
                    RagEvalRun.id == run.id,
                    RagEvalRun.status == "queued",
                )
                .values(
                    status="cancelled",
                    stage="finished",
                    completed_at=now,
                    cancellation_requested_at=now,
                    cancel_requested=False,
                )
                .execution_options(synchronize_session=False)
            )
            if queued_result.rowcount == 0:
                running_result = await session.exec(
                    update(RagEvalRun)
                    .where(
                        RagEvalRun.id == run.id,
                        RagEvalRun.status == "running",
                    )
                    .values(
                        cancel_requested=True,
                        cancellation_requested_at=now,
                    )
                    .execution_options(synchronize_session=False)
                )
                if running_result.rowcount == 0:
                    await session.rollback()
                    await session.refresh(run)
                    raise ValueError("Cannot cancel a finished RAG evaluation run")
        await session.commit()
        await session.refresh(run)
        return run
    except Exception:
        if session.in_transaction():
            await session.rollback()
        raise


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
    example_ids = [item.example_id for item in buffered]
    if len(example_ids) != len(set(example_ids)):
        raise ValueError("Final RAG evaluation results contain duplicate example_id")

    try:
        locked_result = await session.exec(
            select(RagEvalRun)
            .where(RagEvalRun.id == run.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        locked_run = locked_result.first()
        if locked_run is None:
            raise ValueError("RAG evaluation run does not exist")
        if locked_run.status != "running":
            raise ValueError("Only a running evaluation can be finalized")
        if locked_run.cancel_requested:
            raise RagEvalFinalizationCancelled()
        if len(buffered) != locked_run.total_examples:
            raise ValueError(
                "Successful finalization requires exactly "
                f"{locked_run.total_examples} query results"
            )

        rows = [
            RagEvalQueryResult(
                run_id=locked_run.id,
                **item.model_dump(mode="json"),
            )
            for item in buffered
        ]
        session.add_all(rows)
        await session.flush()
        locked_run.status = "completed"
        locked_run.stage = "finished"
        locked_run.progress = 100.0
        locked_run.completed_examples = locked_run.total_examples
        locked_run.completed_at = utc_now()
        locked_run.cancel_requested = False
        locked_run.resolved_pipeline_snapshot = dict(resolved_pipeline_snapshot)
        locked_run.overall_metrics = dict(overall_metrics)
        locked_run.category_metrics = dict(category_metrics)
        session.add(locked_run)
        await session.flush()
        await session.commit()
        await session.refresh(locked_run)
        return locked_run
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
