"""Business orchestration for asynchronous RAG evaluation runs."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any
from sqlmodel.ext.asyncio.session import AsyncSession
from app.airag.evaluation.rag_eval_runtime import (
    RagEvaluationCancelled,
    cleanup_rag_eval_graph_scope,
    create_legacy_rag_eval_runtime,
)
from app.airag.evaluation.rag_eval_strategies import EVALUATION_STRATEGIES
from app.airag.evaluation.ragas_helpers import RagasEvaluator
from app.db.db import AsyncSessionLocal, AsyncSession
from app.models.rag_eval import RagEvalPairProfile, RagEvalRun
from app.models.users import User
from app.repositories import chunking_profiles_repo, rag_eval_repo, rag_profiles_repo
from app.services.llm_models_service import normalize_llm_selection
from app.schemas.rag_eval_schemas import (
    RagEvalPairProfileCreate,
    RagEvalPairProfileCreateRequest,
    RagEvalPairProfileRead,
    RagEvalPairProfileUpdate,
    RagEvalPairProfileUpdateRequest,
    RagEvalQueryResultCreate,
    RagEvalQueryResultRead,
    RagEvalRunCreate,
    RagEvalRunDetailRead,
    RagEvalRunRead,
    RagEvalRunStartRequest,
    validate_rag_eval_retrieval_config,
)

_tasks: dict[int, asyncio.Task] = {}


def _pair_read(profile: RagEvalPairProfile) -> RagEvalPairProfileRead:
    """
    Convert a RAG evaluation pair profile to its read schema representation.
    Args:
        profile (RagEvalPairProfile): The RAG evaluation pair profile to convert.
    Returns:
        RagEvalPairProfileRead: The read schema representation of the profile.
    """
    return RagEvalPairProfileRead.model_validate(profile, from_attributes=True)


def _run_read(run: RagEvalRun) -> RagEvalRunRead:
    """
    Convert a RAG evaluation run to its read schema representation.
    Args:
        run (RagEvalRun): The RAG evaluation run to convert.
    Returns:
        RagEvalRunRead: The read schema representation of the run.
    """
    return RagEvalRunRead.model_validate(run, from_attributes=True)


async def create_rag_eval_pair_profile_srvc(data: RagEvalPairProfileCreateRequest, 
                                            session: AsyncSession, 
                                            current_user: User) -> RagEvalPairProfileRead:
    """
    Create a new RAG evaluation pair profile.
    Args:
        data (RagEvalPairProfileCreateRequest): The data for the new RAG 
            evaluation pair profile.
        session (AsyncSession): The database session.
        current_user (User): The current user creating the profile.
    Returns:
        RagEvalPairProfileRead: The read schema representation of the newly 
        created profile.
    Raises:
        ValueError: If the referenced RAG or chunking profile is not found.
    """
    rag = await rag_profiles_repo.get_rag_profile_by_id(data.rag_profile_id, session)
    if rag is None:
        raise ValueError("RAG profile not found")
    chunking = await chunking_profiles_repo.get_chunking_profile_by_id(data.chunking_profile_id, session)
    if chunking is None:
        raise ValueError("Chunking profile not found")
    EVALUATION_STRATEGIES.require(rag.strategy)
    validate_rag_eval_retrieval_config(data.retrieval_config, rag.strategy)
    profile = await rag_eval_repo.create_rag_eval_pair_profile(
        RagEvalPairProfileCreate(**data.model_dump(), created_by_user_id=current_user.id), session
    )
    return _pair_read(profile)


async def list_rag_eval_pair_profiles_srvc(session: AsyncSession,
                                            *,
                                            skip: int, 
                                            limit: int) -> list[RagEvalPairProfileRead]:
    """
    List RAG evaluation pair profiles.
    Args:
        session (AsyncSession): The database session.
        skip (int): The number of profiles to skip.
        limit (int): The maximum number of profiles to return.
    Returns:
        list[RagEvalPairProfileRead]: A list of RAG evaluation pair profiles.
    """
    return [_pair_read(item) for item in await rag_eval_repo.list_rag_eval_pair_profiles(session, 
                                                                                         skip=skip, 
                                                                                         limit=limit)]


async def get_rag_eval_pair_profile_srvc(pair_id: int, 
                                         session: AsyncSession) -> RagEvalPairProfileRead:
    """
    Get a RAG evaluation pair profile by ID.
    Args:
        pair_id (int): The ID of the RAG evaluation pair profile.
        session (AsyncSession): The database session.
    Returns:
        RagEvalPairProfileRead: The read schema representation of the RAG evaluation pair profile.
    """
    profile = await rag_eval_repo.get_rag_eval_pair_profile_by_id(pair_id, session)
    if profile is None:
        raise ValueError("RAG evaluation pair profile not found")
    return _pair_read(profile)


async def update_rag_eval_pair_profile_srvc(pair_id: int, 
                                            data: RagEvalPairProfileUpdateRequest, 
                                            session: AsyncSession, 
                                            current_user: User) -> RagEvalPairProfileRead:
    """
    Update a RAG evaluation pair profile.
    Args:
        pair_id (int): The ID of the RAG evaluation pair profile to update.
        data (RagEvalPairProfileUpdateRequest): The data to update the 
            profile with.
        session (AsyncSession): The database session.
        current_user (User): The current user performing the update.
    Returns:
        RagEvalPairProfileRead: The read schema representation of the 
        updated profile.
    Raises:
        ValueError: If the RAG evaluation pair profile is not found.
    """
    profile = await rag_eval_repo.get_rag_eval_pair_profile_by_id(pair_id, session)
    if profile is None:
        raise ValueError("RAG evaluation pair profile not found")
    if data.retrieval_config is not None:
        rag = await rag_profiles_repo.get_rag_profile_by_id(profile.rag_profile_id, session)
        if rag is None:
            raise ValueError("RAG evaluation pair profile references a missing profile")
        validate_rag_eval_retrieval_config(data.retrieval_config, rag.strategy)
    updated = await rag_eval_repo.update_rag_eval_pair_profile(profile, 
                                                               RagEvalPairProfileUpdate(**data.model_dump(exclude_unset=True), last_edit_by_user_id=current_user.id), 
                                                               session)
    return _pair_read(updated)


async def delete_rag_eval_pair_profile_srvc(pair_id: int, session: AsyncSession) -> None:
    """
    Delete a RAG evaluation pair profile.
    Args:
        pair_id (int): The ID of the RAG evaluation pair profile to delete.
        session (AsyncSession): The database session.
    Raises:
        ValueError: If the RAG evaluation pair profile is not found.
    """
    profile = await rag_eval_repo.get_rag_eval_pair_profile_by_id(pair_id, session)
    if profile is None:
        raise ValueError("RAG evaluation pair profile not found")
    await rag_eval_repo.delete_rag_eval_pair_profile(profile, session)


def _profile_snapshot(profile: Any) -> dict[str, Any]:
    """
    Create a snapshot of a profile.
    Args:
        profile (Any): The profile object to create a snapshot of.
    Returns:
        dict[str, Any]: A dictionary containing the profile snapshot.
    """
    return {"id": profile.id, "name": profile.name, "strategy": profile.strategy, "config": dict(profile.config)}


async def start_rag_eval_run_srvc(pair_id: int, 
                                  data: RagEvalRunStartRequest, 
                                  session: AsyncSession) -> RagEvalRunRead:
    """
    Start a new RAG evaluation run for a given pair profile.
    Args:
        pair_id (int): The ID of the RAG evaluation pair profile to run.
        data (RagEvalRunStartRequest): The data for the new RAG 
            evaluation run.
        session (AsyncSession): The database session.
    Returns:
        RagEvalRunRead: The read schema representation of the newly 
        created run.
    Raises:
        ValueError: If the RAG evaluation pair profile is not found or 
        if it references a missing RAG or chunking profile.
    """
    pair = await rag_eval_repo.get_rag_eval_pair_profile_by_id(pair_id, session)
    if pair is None:
        raise ValueError("RAG evaluation pair profile not found")
    rag = await rag_profiles_repo.get_rag_profile_by_id(pair.rag_profile_id, session)
    chunking = await chunking_profiles_repo.get_chunking_profile_by_id(pair.chunking_profile_id, session)
    if rag is None or chunking is None:
        raise ValueError("RAG evaluation pair profile references a missing profile")
    EVALUATION_STRATEGIES.require(rag.strategy)
    validate_rag_eval_retrieval_config(pair.retrieval_config, rag.strategy)
    answer_selection = normalize_llm_selection(
        data.answer_llm_provider, data.answer_llm_model
    )
    judge_selection = normalize_llm_selection(
        data.judge_llm_provider, data.judge_llm_model
    )
    run = await rag_eval_repo.create_rag_eval_run(RagEvalRunCreate(
        pair_profile_id=pair_id, k=data.k,
        rag_profile_snapshot=_profile_snapshot(rag),
        chunking_profile_snapshot=_profile_snapshot(chunking),
        retrieval_config_snapshot=deepcopy(pair.retrieval_config),
        answer_generation_model_snapshot={
            "llm_provider": answer_selection["provider"],
            "llm_model": answer_selection["model"],
            "temperature": 0,
            "prompt_version": "grounded_answer_v1",
        },
        evaluation_model_snapshot={
            "llm_provider": judge_selection["provider"],
            "llm_model": judge_selection["model"],
            "embedding_model": data.judge_embedding_model,
        },
    ), session)
    if run.id is not None:
        _tasks[run.id] = asyncio.create_task(_execute_rag_eval_run(run.id))
    return _run_read(run)


async def _execute_rag_eval_run(run_id: int) -> None:
    """
    Execute a RAG evaluation run.
    Args:
        run_id (int): The ID of the RAG evaluation run to execute.
    Returns:
        None
    """
    async with AsyncSessionLocal() as session:
        run = await rag_eval_repo.get_rag_eval_run_by_id(run_id, session)
        if run is None or run.cancel_requested:
            return
        try:
            run = await rag_eval_repo.mark_rag_eval_run_running(run, session)
            runtime = create_legacy_rag_eval_runtime()
            result = await runtime.run(
                run_id=run.id,
                rag_snapshot=run.rag_profile_snapshot,
                chunking_snapshot=run.chunking_profile_snapshot,
                retrieval_config_snapshot=run.retrieval_config_snapshot,
                k=run.k,
                stage_callback=lambda stage: rag_eval_repo.update_rag_eval_run(
                    run, session, stage=stage
                ),
                should_cancel=lambda: _is_rag_eval_run_cancel_requested(run, session),
            )
            await session.refresh(run)
            if run.cancel_requested:
                await rag_eval_repo.mark_rag_eval_run_cancelled(run, session)
                return
            evaluator = RagasEvaluator.from_model_selection(
                run.evaluation_model_snapshot["llm_provider"], run.evaluation_model_snapshot["llm_model"], run.evaluation_model_snapshot["embedding_model"]
            )
            await rag_eval_repo.update_rag_eval_run(run, session, stage="judging")
            ragas = await evaluator.evaluate(result)
            ragas_by_id = {item.evaluation_id: item.metric_scores for item in ragas.results}
            for row in result.results:
                await rag_eval_repo.create_rag_eval_query_result(RagEvalQueryResultCreate(
                    run_id=run.id, evaluation_id=row.evaluation_id, query=row.query,
                    reference_answer=row.reference, answer=row.answer,
                    retrieved_contexts=list(row.retrieved_contexts),
                    retrieved_evaluation_ids=[value for ids in row.retrieved_evaluation_ids for value in ids],
                    reference_rank=row.first_relevant_rank, hit_at_k=row.hit_at_k,
                    mrr_contribution=row.reciprocal_rank_at_k, ragas_metrics=ragas_by_id.get(row.evaluation_id, {}),
                ), session)
            await rag_eval_repo.mark_rag_eval_run_completed(run, session, 
                                                            hit_rate_at_k=result.hit_rate_at_k, 
                                                            mrr_at_k=result.mrr_at_k, 
                                                            ragas_metrics=ragas.metric_means)
        except RagEvaluationCancelled:
            await rag_eval_repo.mark_rag_eval_run_cancelled(run, session)
        except Exception as exc:
            if run.status in {"queued", "running"}:
                await rag_eval_repo.mark_rag_eval_run_failed(run, str(exc), session)
        finally:
            _tasks.pop(run_id, None)


async def _is_rag_eval_run_cancel_requested(run: RagEvalRun, session: AsyncSession) -> bool:
    """
    Check if a RAG evaluation run has a cancellation requested.
    Args:
        run (RagEvalRun): The RAG evaluation run.
        session (AsyncSession): The database session.
    Returns:
        bool: True if cancellation has been requested, False otherwise.
    """
    await session.refresh(run)
    return bool(run.cancel_requested)


async def list_rag_eval_runs_srvc(session: AsyncSession, 
                                  *, 
                                  skip: int, 
                                  limit: int, 
                                  pair_profile_id: int | None = None, 
                                  status: str | None = None) -> list[RagEvalRunRead]:
    """
    List RAG evaluation runs with optional filtering by pair profile ID 
    and status.
    Args:
        session (AsyncSession): The database session.
        skip (int): The number of runs to skip.
        limit (int): The maximum number of runs to return.
        pair_profile_id (int | None): Optional filter for runs associated 
            with a specific pair profile ID.
        status (str | None): Optional filter for runs with a specific 
            status.
    Returns:
        list[RagEvalRunRead]: A list of RAG evaluation runs.
    """
    return [_run_read(item) for item in await rag_eval_repo.list_rag_eval_runs(session, 
                                                                               skip=skip, 
                                                                               limit=limit, 
                                                                               pair_profile_id=pair_profile_id, 
                                                                               status=status)]


async def get_rag_eval_run_srvc(run_id: int, 
                                session: AsyncSession) -> RagEvalRunDetailRead:
    """
    Get details of a specific RAG evaluation run.
    Args:
        run_id (int): The ID of the RAG evaluation run.
        session (AsyncSession): The database session.
    Returns:
        RagEvalRunDetailRead: The details of the RAG evaluation run.
    """
    run = await rag_eval_repo.get_rag_eval_run_by_id(run_id, session)
    if run is None:
        raise ValueError("RAG evaluation run not found")
    rows = await rag_eval_repo.list_rag_eval_query_results(run_id, session)
    return RagEvalRunDetailRead(**_run_read(run).model_dump(), query_results=[RagEvalQueryResultRead.model_validate(row, from_attributes=True) for row in rows])


async def cancel_rag_eval_run_srvc(run_id: int, 
                                   session: AsyncSession) -> RagEvalRunRead:
    """
    Cancel a RAG evaluation run.
    Args:
        run_id (int): The ID of the RAG evaluation run to cancel.
        session (AsyncSession): The database session.
    Returns:
        RagEvalRunRead: The read schema representation of the cancelled run.
    Raises:
        ValueError: If the RAG evaluation run is not found.
    """
    run = await rag_eval_repo.get_rag_eval_run_by_id(run_id, session)
    if run is None:
        raise ValueError("RAG evaluation run not found")
    if run.status == "queued":
        run = await rag_eval_repo.mark_rag_eval_run_cancelled(run, session)
    else:
        run = await rag_eval_repo.request_rag_eval_run_cancel(run, session)
    return _run_read(run)


async def fail_interrupted_rag_eval_runs_srvc() -> None:
    """
    Fail all interrupted RAG evaluation runs.
    This function marks all runs with status "queued" or "running" as
    failed.
    Args:
        None
    Returns:
        None
    """
    async with AsyncSessionLocal() as session:
        for run in await rag_eval_repo.list_rag_eval_runs(session, skip=0, limit=10_000):
            if run.status in {"queued", "running"}:
                if run.rag_profile_snapshot.get("strategy") == "graphrag":
                    try:
                        # Delete the temp graph
                        await cleanup_rag_eval_graph_scope(run.id)
                    except Exception:
                        # Preserve this active run for the next startup retry: terminating it
                        # here would leave an unreachable temporary graph generation behind.
                        await rag_eval_repo.update_rag_eval_run(
                            run, session, stage="cleanup_pending"
                        )
                        continue
                await rag_eval_repo.mark_rag_eval_run_failed(run, "RAG evaluation interrupted by application restart", session)
