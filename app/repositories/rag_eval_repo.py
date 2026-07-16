from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.rag_eval import RagEvalPairProfile, RagEvalQueryResult, RagEvalRun
from app.repositories.helpers import commit_and_refresh, commit_delete, utc_now
from app.schemas.rag_eval_schemas import (
    RagEvalPairProfileCreate,
    RagEvalPairProfileUpdate,
    RagEvalQueryResultCreate,
    RagEvalRunCreate,
)


ACTIVE_RAG_EVAL_RUN_STATUSES = {"queued", "running"}
TERMINAL_RAG_EVAL_RUN_STATUSES = {"completed", "failed", "cancelled"}
_RAG_EVAL_RUN_TRANSITIONS = {
    "queued": {"running", "cancelled", "failed"},
    "running": {"completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


async def get_rag_eval_pair_profile_by_id(
    pair_profile_id: int, session: AsyncSession
) -> RagEvalPairProfile | None:
    """
    Get a RAG evaluation pair profile by its ID.
    Args:
        pair_profile_id (int): The ID of the RAG evaluation pair profile.
        session (AsyncSession): The database session.
    Returns:
        RagEvalPairProfile | None: The RAG evaluation pair profile if found, else None
    """
    return await session.get(RagEvalPairProfile, pair_profile_id)


async def get_rag_eval_pair_profile_by_name(
    name: str, session: AsyncSession
) -> RagEvalPairProfile | None:
    """
    Get a RAG evaluation pair profile by its name.
    Args:
        name (str): The name of the RAG evaluation pair profile.
        session (AsyncSession): The database session.
    Returns:
        RagEvalPairProfile | None: The RAG evaluation pair profile if found, else None
    """
    result = await session.exec(
        select(RagEvalPairProfile).where(RagEvalPairProfile.name == name)
    )
    return result.first()


async def ensure_rag_eval_pair_profile_name_available(
    name: str, session: AsyncSession, exclude_pair_profile_id: int | None = None
) -> None:
    """
    Ensure that a RAG evaluation pair profile name is available (not already taken).
    Args:
        name (str): The name to check for availability.
        session (AsyncSession): The database session.
        exclude_pair_profile_id (int | None): An optional pair profile ID to exclude from the check (useful when updating an existing profile).
    Returns:
        None
    Raises:
        ValueError: If the name is already taken by another profile.
    """
    existing = await get_rag_eval_pair_profile_by_name(name, session)
    if existing is not None and existing.id != exclude_pair_profile_id:
        raise ValueError("RAG evaluation pair profile name already exists")


async def list_rag_eval_pair_profiles(
    session: AsyncSession, *, skip: int = 0, limit: int = 20
) -> list[RagEvalPairProfile]:
    result = await session.exec(
        select(RagEvalPairProfile)
        .order_by(RagEvalPairProfile.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.all())


async def create_rag_eval_pair_profile(
    profile_in: RagEvalPairProfileCreate, 
    session: AsyncSession
) -> RagEvalPairProfile:
    """
    Create a new RAG evaluation pair profile.
    Args:
        profile_in (RagEvalPairProfileCreate): The input data for 
            creating the profile.
        session (AsyncSession): The database session.
    Returns:
        RagEvalPairProfile: The created RAG evaluation pair profile.
    Raises:
        ValueError: If the profile name is already taken.
    """
    await ensure_rag_eval_pair_profile_name_available(profile_in.name, session)
    return await commit_and_refresh(
        session, RagEvalPairProfile(**profile_in.model_dump())
    )


async def rag_eval_pair_profile_has_runs(pair_profile_id: int, session: AsyncSession) -> bool:
    """
    Check if a RAG evaluation pair profile has any evaluation runs.
    Args:
        pair_profile_id (int): The ID of the RAG evaluation pair profile.
        session (AsyncSession): The database session.
    Returns:
        bool: True if the profile has evaluation runs, False otherwise.
    """
    result = await session.exec(
        select(RagEvalRun.id).where(RagEvalRun.pair_profile_id == pair_profile_id).limit(1)
    )
    return result.first() is not None


async def ensure_rag_eval_pair_profile_mutable(
    profile: RagEvalPairProfile, session: AsyncSession
) -> None:
    """
    Ensure that a RAG evaluation pair profile can be modified.
    Args:
        profile (RagEvalPairProfile): The RAG evaluation pair profile to check.
        session (AsyncSession): The database session.
    Raises:
        ValueError: If the profile is not persisted or has evaluation runs.
    """
    if profile.id is None:
        raise ValueError("RAG evaluation pair profile must be persisted before this operation")
    if await rag_eval_pair_profile_has_runs(profile.id, session):
        raise ValueError("Cannot modify RAG evaluation pair profile that has evaluation runs")


async def update_rag_eval_pair_profile(
    profile: RagEvalPairProfile,
    profile_in: RagEvalPairProfileUpdate,
    session: AsyncSession,
) -> RagEvalPairProfile:
    """
    Update a RAG evaluation pair profile with new values.
    Args:
        profile (RagEvalPairProfile): The existing RAG evaluation pair 
            profile to update.
        profile_in (RagEvalPairProfileUpdate): The new values for the 
            profile.
        session (AsyncSession): The database session.
    Returns:
        RagEvalPairProfile: The updated RAG evaluation pair profile.
    """
    await ensure_rag_eval_pair_profile_mutable(profile, session)
    values = profile_in.model_dump(exclude_unset=True)
    if values.get("name") is not None:
        await ensure_rag_eval_pair_profile_name_available(values["name"], session, profile.id)
    for key, value in values.items():
        setattr(profile, key, value)
    profile.last_updated = utc_now()
    return await commit_and_refresh(session, profile)


async def delete_rag_eval_pair_profile(
    profile: RagEvalPairProfile, session: AsyncSession
) -> None:
    """
    Delete a RAG evaluation pair profile.
    Args:
        profile (RagEvalPairProfile): The RAG evaluation pair profile to delete.
        session (AsyncSession): The database session.
    Raises:
        ValueError: If the profile is not mutable.
    """
    await ensure_rag_eval_pair_profile_mutable(profile, session)
    await commit_delete(session, profile)


async def get_rag_eval_run_by_id(run_id: int, session: AsyncSession) -> RagEvalRun | None:
    """
    Get a RAG evaluation run by its ID.
    Args:
        run_id (int): The ID of the RAG evaluation run.
        session (AsyncSession): The database session.
    Returns:
        RagEvalRun | None: The RAG evaluation run if found, else None.
    """
    return await session.get(RagEvalRun, run_id)


async def get_active_rag_eval_run(
    pair_profile_id: int, session: AsyncSession
) -> RagEvalRun | None:
    """
    Get a RAG evaluation run that is currently active (queued or running) 
    for a given pair profile ID.
    Args:
        pair_profile_id (int): The ID of the RAG evaluation pair profile.
        session (AsyncSession): The database session.
    Returns:
        RagEvalRun | None: The active RAG evaluation run if found, else None.
    """
    result = await session.exec(
        select(RagEvalRun)
        .where(
            RagEvalRun.pair_profile_id == pair_profile_id,
            RagEvalRun.status.in_(ACTIVE_RAG_EVAL_RUN_STATUSES),
        )
        .order_by(RagEvalRun.id.desc())
    )
    return result.first()


async def list_rag_eval_runs(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 20,
    pair_profile_id: int | None = None,
    status: str | None = None,
) -> list[RagEvalRun]:
    """
    List RAG evaluation runs with optional filtering by pair profile ID and 
    status.
    Args:
        session (AsyncSession): The database session.
        skip (int, optional): The number of records to skip. Defaults to 0.
        limit (int, optional): The maximum number of records to return. Defaults to 20.
        pair_profile_id (int | None, optional): The ID of the RAG evaluation pair profile to filter by. Defaults to None.
        status (str | None, optional): The status to filter by. Defaults to None.
    Returns:
        list[RagEvalRun]: The list of RAG evaluation runs matching the filters.
    """
    statement = select(RagEvalRun)
    if pair_profile_id is not None:
        statement = statement.where(RagEvalRun.pair_profile_id == pair_profile_id)
    if status is not None:
        statement = statement.where(RagEvalRun.status == status)
    result = await session.exec(statement.order_by(RagEvalRun.id.desc()).offset(skip).limit(limit))
    return list(result.all())


async def create_rag_eval_run(
    run_in: RagEvalRunCreate, session: AsyncSession
) -> RagEvalRun:
    """
    Create a new RAG evaluation run.
    Args:
        run_in (RagEvalRunCreate): The data for the new RAG evaluation run.
        session (AsyncSession): The database session.
    Returns:
        RagEvalRun: The newly created RAG evaluation run.
    """
    if await get_active_rag_eval_run(run_in.pair_profile_id, session) is not None:
        raise ValueError("RAG evaluation pair profile already has an active evaluation run")
    return await commit_and_refresh(session, RagEvalRun(**run_in.model_dump()))


def _validate_rag_eval_run_transition(current_status: str, next_status: str) -> None:
    """
    Validate that a transition from the current status to the next status 
    is allowed.
    Args:
        current_status (str): The current status of the RAG evaluation run.
        next_status (str): The desired next status of the RAG evaluation run.
    Raises:
        ValueError: If the transition is not allowed.
    """
    if next_status not in _RAG_EVAL_RUN_TRANSITIONS.get(current_status, set()):
        raise ValueError(
            f"Invalid RAG evaluation run status transition: {current_status!r} -> {next_status!r}"
        )


async def update_rag_eval_run(
    run: RagEvalRun, 
    session: AsyncSession, 
    **values: Any
) -> RagEvalRun:
    """
    Update a RAG evaluation run with new values.
    Args:
        run (RagEvalRun): The existing RAG evaluation run to update.
        session (AsyncSession): The database session.
        **values: The new values to update the run with.
    Returns:
        RagEvalRun: The updated RAG evaluation run.
    """
    next_status = values.get("status")
    if next_status is not None and next_status != run.status:
        _validate_rag_eval_run_transition(run.status, next_status)
    for key, value in values.items():
        setattr(run, key, value)
    return await commit_and_refresh(session, run)


async def mark_rag_eval_run_running(run: RagEvalRun, session: AsyncSession) -> RagEvalRun:
    """
    Mark a RAG evaluation run as running.
    Args:
        run (RagEvalRun): The RAG evaluation run to mark as running.
        session (AsyncSession): The database session.
    Returns:
        RagEvalRun: The updated RAG evaluation run.
    """
    return await update_rag_eval_run(
        run, 
        session, 
        status="running", 
        stage="preparing", 
        started_at=utc_now(), 
        cancel_requested=False
    )


async def mark_rag_eval_run_completed(
    run: RagEvalRun,
    session: AsyncSession,
    *,
    hit_rate_at_k: float,
    mrr_at_k: float,
    ragas_metrics: dict[str, Any],
) -> RagEvalRun:
    """
    Mark a RAG evaluation run as completed.
    Args:
        run (RagEvalRun): The RAG evaluation run to mark as completed.
        session (AsyncSession): The database session.
        hit_rate_at_k (float): The hit rate at k for the evaluation run.
        mrr_at_k (float): The mean reciprocal rank at k for the evaluation run.
        ragas_metrics (dict[str, Any]): The RAGAS metrics for the evaluation run.
    Returns:
        RagEvalRun: The updated RAG evaluation run.
    """
    return await update_rag_eval_run(
        run,
        session,
        status="completed",
        stage="finished",
        completed_at=utc_now(),
        cancel_requested=False,
        aggregate_hit_rate_at_k=hit_rate_at_k,
        aggregate_mrr_at_k=mrr_at_k,
        aggregate_ragas_metrics=ragas_metrics,
    )


async def mark_rag_eval_run_failed(
    run: RagEvalRun, detail: str, session: AsyncSession
) -> RagEvalRun:
    """
    Mark a RAG evaluation run as failed.
    Args:
        run (RagEvalRun): The RAG evaluation run to mark as failed.
        detail (str): The failure detail message.
        session (AsyncSession): The database session.
    Returns:
        RagEvalRun: The updated RAG evaluation run.
    """
    return await update_rag_eval_run(
        run,
        session,
        status="failed",
        stage="finished",
        completed_at=utc_now(),
        failure_detail=detail,
        cancel_requested=False,
    )


async def mark_rag_eval_run_cancelled(run: RagEvalRun, session: AsyncSession) -> RagEvalRun:
    """
    Mark a RAG evaluation run as cancelled.
    Args:
        run (RagEvalRun): The RAG evaluation run to mark as cancelled.
        session (AsyncSession): The database session.
    Returns:
        RagEvalRun: The updated RAG evaluation run.
    """
    return await update_rag_eval_run(
        run,
        session,
        status="cancelled",
        stage="finished",
        completed_at=utc_now(),
        failure_detail="RAG evaluation run cancelled",
        cancel_requested=False,
    )


async def request_rag_eval_run_cancel(run: RagEvalRun, session: AsyncSession) -> RagEvalRun:
    """
    Request cancellation of a RAG evaluation run.
    Args:
        run (RagEvalRun): The RAG evaluation run to request cancellation for.
        session (AsyncSession): The database session.
    Returns:
        RagEvalRun: The updated RAG evaluation run.
    """
    if run.status in TERMINAL_RAG_EVAL_RUN_STATUSES:
        raise ValueError("Cannot cancel a finished RAG evaluation run")
    return await update_rag_eval_run(run, session, cancel_requested=True)


async def create_rag_eval_query_result(
    result_in: RagEvalQueryResultCreate, session: AsyncSession
) -> RagEvalQueryResult:
    """
    Create a new RAG evaluation query result.
    Args:
        result_in (RagEvalQueryResultCreate): The data for the new RAG evaluation query result.
        session (AsyncSession): The database session.
    Returns:
        RagEvalQueryResult: The newly created RAG evaluation query result.
    """
    return await commit_and_refresh(session, RagEvalQueryResult(**result_in.model_dump()))


async def list_rag_eval_query_results(
    run_id: int, session: AsyncSession
) -> list[RagEvalQueryResult]:
    """
    List all RAG evaluation query results for a given run.
    Args:
        run_id (int): The ID of the RAG evaluation run.
        session (AsyncSession): The database session.
    Returns:
        list[RagEvalQueryResult]: A list of RAG evaluation query results.
    """
    result = await session.exec(
        select(RagEvalQueryResult)
        .where(RagEvalQueryResult.run_id == run_id)
        .order_by(RagEvalQueryResult.id.asc())
    )
    return list(result.all())
