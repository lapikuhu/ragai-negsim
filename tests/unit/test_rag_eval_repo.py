from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Index
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.rag_eval import (
    RagEvalConfiguration,
    RagEvalQueryResult,
    RagEvalRun,
)
from app.repositories import rag_eval_repo
from app.schemas.rag_eval_schemas import (
    RagEvalConfigurationCreate,
    RagEvalConfigurationUpdate,
    RagEvalQueryResultCreate,
)


COMPONENT_SELECTIONS = {
    name: {"provider": "openai", "model": "gpt-4o-mini"}
    for name in (
        "document_grader",
        "query_rewriter",
        "answer_generator",
        "hallucination_grader",
        "answer_grader",
        "fallback_generator",
    )
}


def configuration_input(name: str = "baseline evaluation") -> RagEvalConfigurationCreate:
    return RagEvalConfigurationCreate.model_validate(
        {
            "name": name,
            "chunking": {
                "strategy": "recursive",
                "chunk_size": 1000,
                "chunk_overlap": 200,
            },
            "rag": {
                "strategy": "crag",
                "retrieval_embedding_model": "text-embedding-3-small",
                "top_k": 4,
                "reranker": "none",
                "top_n": 4,
                "rewrite_limit": 2,
                **COMPONENT_SELECTIONS,
            },
            "metrics": {
                "k": 4,
                "ragas_judge": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                },
                "judge_embedding_model": "text-embedding-3-small",
            },
            "created_by_user_id": 7,
        }
    )


def query_result(example_id: str = "direct-001") -> RagEvalQueryResultCreate:
    return RagEvalQueryResultCreate(
        example_id=example_id,
        category="direct_retrieval",
        answerable=True,
        query="What is BATNA?",
        reference_answer="The best alternative to a negotiated agreement.",
        actual_answer="It is the best alternative.",
        final_chunks=[
            {
                "rank": 1,
                "content": "BATNA means best alternative.",
                "metadata": {"source": "support_1.md"},
            }
        ],
        first_relevant_rank=1,
        hit_at_k=True,
        mrr_at_k=1.0,
        faithfulness=0.9,
        answer_relevancy=0.8,
        context_precision=0.7,
        context_recall=0.6,
        answer_correctness=0.85,
    )


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        yield session


def test_target_models_have_complete_shape_without_profile_foreign_keys():
    configuration_columns = set(RagEvalConfiguration.__table__.c.keys())
    run_columns = set(RagEvalRun.__table__.c.keys())
    result_columns = set(RagEvalQueryResult.__table__.c.keys())

    assert {"name", "chunking", "rag", "metrics"} <= configuration_columns
    assert "rag_profile_id" not in configuration_columns
    assert "chunking_profile_id" not in configuration_columns
    assert {
        "configuration_id",
        "configuration_snapshot",
        "suite_version",
        "suite_content_hash",
        "resolved_pipeline_snapshot",
        "progress",
        "completed_examples",
        "total_examples",
        "cancellation_requested_at",
        "failure_code",
        "failure_message",
        "overall_metrics",
        "category_metrics",
    } <= run_columns
    assert {
        "example_id",
        "category",
        "answerable",
        "actual_answer",
        "final_chunks",
        "first_relevant_rank",
        "hit_at_k",
        "mrr_at_k",
        "successful_abstention",
        "false_positive_context",
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "answer_correctness",
    } <= result_columns

    constraints = {
        constraint.name: constraint
        for constraint in RagEvalRun.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "cleanup_pending" in str(constraints["ck_rag_eval_run_valid_stage"].sqltext)

    global_running = next(
        index
        for index in RagEvalRun.__table__.indexes
        if isinstance(index, Index) and index.name == "uq_rag_eval_run_global_running"
    )
    ddl = str(
        __import__("sqlalchemy").schema.CreateIndex(global_running).compile(
            dialect=postgresql.dialect()
        )
    )
    assert "UNIQUE INDEX uq_rag_eval_run_global_running" in ddl
    assert "WHERE status = 'running'" in ddl


def test_fifo_claim_statement_uses_postgres_skip_locked_and_deterministic_order():
    statement = rag_eval_repo._next_queued_rag_eval_run_statement()
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "ORDER BY ragevalrun.queued_at ASC, ragevalrun.id ASC" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql


@pytest.mark.asyncio
async def test_configuration_is_editable_after_run_but_delete_is_restricted(db_session):
    configuration = await rag_eval_repo.create_rag_eval_configuration(
        configuration_input(), db_session
    )
    await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version="2026.1",
        suite_content_hash="abc123",
        total_examples=80,
        session=db_session,
    )

    updated = await rag_eval_repo.update_rag_eval_configuration(
        configuration,
        RagEvalConfigurationUpdate(
            name="renamed evaluation",
            last_edit_by_user_id=8,
        ),
        db_session,
    )

    assert updated.name == "renamed evaluation"
    with pytest.raises(ValueError, match="referenced by evaluation runs"):
        await rag_eval_repo.delete_rag_eval_configuration(updated, db_session)


@pytest.mark.asyncio
async def test_configuration_names_are_unique_and_listed_with_pagination(db_session):
    await rag_eval_repo.create_rag_eval_configuration(
        configuration_input("alpha evaluation"), db_session
    )
    await rag_eval_repo.create_rag_eval_configuration(
        configuration_input("beta evaluation"), db_session
    )

    with pytest.raises(ValueError, match="name already exists"):
        await rag_eval_repo.create_rag_eval_configuration(
            configuration_input("alpha evaluation"), db_session
        )

    page = await rag_eval_repo.list_rag_eval_configurations(
        db_session, skip=1, limit=1
    )
    assert [item.name for item in page] == ["alpha evaluation"]


@pytest.mark.asyncio
async def test_enqueue_stores_an_immutable_normalized_configuration_snapshot(db_session):
    configuration = await rag_eval_repo.create_rag_eval_configuration(
        configuration_input(), db_session
    )
    run = await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version="2026.1",
        suite_content_hash="abc123",
        total_examples=80,
        session=db_session,
    )
    original_snapshot = run.configuration_snapshot

    await rag_eval_repo.update_rag_eval_configuration(
        configuration,
        RagEvalConfigurationUpdate(
            chunking={
                "strategy": "recursive",
                "chunk_size": 700,
                "chunk_overlap": 100,
            },
            last_edit_by_user_id=8,
        ),
        db_session,
    )
    await db_session.refresh(run)

    assert run.configuration_snapshot == original_snapshot
    assert run.configuration_snapshot["chunking"]["chunk_size"] == 1000
    assert set(run.configuration_snapshot) == {"name", "chunking", "rag", "metrics"}
    assert run.status == "queued"
    assert run.stage == "queued"
    assert run.progress == 0
    assert run.completed_examples == 0
    assert run.total_examples == 80


@pytest.mark.asyncio
async def test_multiple_queued_runs_are_allowed_and_claimed_fifo(db_session):
    configuration = await rag_eval_repo.create_rag_eval_configuration(
        configuration_input(), db_session
    )
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    later = await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version="2026.1",
        suite_content_hash="later",
        total_examples=80,
        session=db_session,
    )
    earlier = await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version="2026.1",
        suite_content_hash="earlier",
        total_examples=80,
        session=db_session,
    )
    later.queued_at = base + timedelta(seconds=1)
    earlier.queued_at = base
    await db_session.commit()

    claimed = await rag_eval_repo.claim_next_rag_eval_run(db_session)

    assert claimed is not None
    assert claimed.id == earlier.id
    assert claimed.status == "running"
    assert claimed.stage == "preparing"
    assert await rag_eval_repo.claim_next_rag_eval_run(db_session) is None


@pytest.mark.asyncio
async def test_only_fifo_claim_can_transition_a_queued_run_to_running(db_session):
    configuration = await rag_eval_repo.create_rag_eval_configuration(
        configuration_input(), db_session
    )
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    earliest = await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version="2026.1",
        suite_content_hash="earliest",
        total_examples=1,
        session=db_session,
    )
    later = await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version="2026.1",
        suite_content_hash="later",
        total_examples=1,
        session=db_session,
    )
    earliest.queued_at = base
    later.queued_at = base + timedelta(seconds=1)
    await db_session.commit()

    with pytest.raises(ValueError, match="claim_next_rag_eval_run"):
        await rag_eval_repo.transition_rag_eval_run(
            later,
            "running",
            stage="preparing",
            session=db_session,
        )
    await db_session.refresh(later)
    assert later.status == "queued"
    claimed = await rag_eval_repo.claim_next_rag_eval_run(db_session)
    assert claimed is not None
    assert claimed.id == earliest.id
    assert claimed.status == "running"
    await db_session.refresh(later)
    assert later.status == "queued"


@pytest.mark.asyncio
async def test_queued_cancellation_is_terminal_and_never_claimed(db_session):
    configuration = await rag_eval_repo.create_rag_eval_configuration(
        configuration_input(), db_session
    )
    cancelled = await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version="2026.1",
        suite_content_hash="cancelled",
        total_examples=80,
        session=db_session,
    )
    eligible = await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version="2026.1",
        suite_content_hash="eligible",
        total_examples=80,
        session=db_session,
    )

    await rag_eval_repo.request_rag_eval_run_cancel(cancelled, db_session)
    claimed = await rag_eval_repo.claim_next_rag_eval_run(db_session)

    assert cancelled.status == "cancelled"
    assert cancelled.completed_at is not None
    assert claimed is not None
    assert claimed.id == eligible.id


@pytest.mark.asyncio
async def test_stale_queued_cancellation_uses_running_cas_without_overwriting_claim(
    db_engine,
):
    async with AsyncSession(db_engine, expire_on_commit=False) as stale_session:
        configuration = await rag_eval_repo.create_rag_eval_configuration(
            configuration_input(), stale_session
        )
        stale_run = await rag_eval_repo.enqueue_rag_eval_run(
            configuration,
            suite_version="2026.1",
            suite_content_hash="race",
            total_examples=1,
            session=stale_session,
        )

        async with AsyncSession(db_engine, expire_on_commit=False) as claim_session:
            claimed = await rag_eval_repo.claim_next_rag_eval_run(claim_session)
            assert claimed is not None

        assert stale_run.status == "queued"
        cancelled = await rag_eval_repo.request_rag_eval_run_cancel(
            stale_run, stale_session
        )

        assert cancelled.status == "running"
        assert cancelled.cancel_requested is True
        assert cancelled.cancellation_requested_at is not None


@pytest.mark.asyncio
async def test_stale_transition_cannot_overwrite_new_terminal_status(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as stale_session:
        configuration = await rag_eval_repo.create_rag_eval_configuration(
            configuration_input(), stale_session
        )
        stale_run = await rag_eval_repo.enqueue_rag_eval_run(
            configuration,
            suite_version="2026.1",
            suite_content_hash="race",
            total_examples=1,
            session=stale_session,
        )
        await rag_eval_repo.claim_next_rag_eval_run(stale_session)

        async with AsyncSession(db_engine, expire_on_commit=False) as winner_session:
            winner = await winner_session.get(RagEvalRun, stale_run.id)
            assert winner is not None
            await rag_eval_repo.transition_rag_eval_run(
                winner,
                "failed",
                stage="finished",
                failure_code="winner",
                session=winner_session,
            )

        assert stale_run.status == "running"
        with pytest.raises(ValueError, match="changed concurrently"):
            await rag_eval_repo.transition_rag_eval_run(
                stale_run,
                "cancelled",
                stage="finished",
                session=stale_session,
            )

        await stale_session.refresh(stale_run)
        assert stale_run.status == "failed"
        assert stale_run.failure_code == "winner"


@pytest.mark.asyncio
async def test_global_running_constraint_allows_many_queued_but_one_running(db_session):
    configuration = await rag_eval_repo.create_rag_eval_configuration(
        configuration_input(), db_session
    )
    first = await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version="2026.1",
        suite_content_hash="first",
        total_examples=80,
        session=db_session,
    )
    second = await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version="2026.1",
        suite_content_hash="second",
        total_examples=80,
        session=db_session,
    )
    first.status = "running"
    second.status = "running"
    db_session.add(first)
    db_session.add(second)

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_transitions_progress_and_restart_helpers(db_session):
    configuration = await rag_eval_repo.create_rag_eval_configuration(
        configuration_input(), db_session
    )
    run = await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version="2026.1",
        suite_content_hash="abc",
        total_examples=80,
        session=db_session,
    )
    await rag_eval_repo.claim_next_rag_eval_run(db_session)

    await rag_eval_repo.update_rag_eval_run_progress(
        run,
        stage="evaluating",
        progress=25.0,
        completed_examples=20,
        total_examples=80,
        session=db_session,
    )
    interrupted = await rag_eval_repo.list_interrupted_rag_eval_runs(db_session)

    assert [item.id for item in interrupted] == [run.id]
    assert run.completed_examples == 20
    assert run.progress == 25.0
    with pytest.raises(ValueError, match="Invalid RAG evaluation run status transition"):
        await rag_eval_repo.transition_rag_eval_run(
            run, "queued", session=db_session
        )

    await rag_eval_repo.transition_rag_eval_run(
        run,
        "failed",
        stage="finished",
        failure_code="restart_interrupted",
        failure_message="Evaluation interrupted by restart",
        session=db_session,
    )
    assert await rag_eval_repo.list_interrupted_rag_eval_runs(db_session) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "immutable_field",
    [
        "configuration_snapshot",
        "configuration_id",
        "queued_at",
        "suite_version",
        "suite_content_hash",
    ],
)
async def test_run_transition_rejects_immutable_fields(
    db_session,
    immutable_field,
):
    configuration = await rag_eval_repo.create_rag_eval_configuration(
        configuration_input(), db_session
    )
    run = await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version="2026.1",
        suite_content_hash="immutable",
        total_examples=1,
        session=db_session,
    )
    original_snapshot = run.configuration_snapshot

    with pytest.raises(ValueError, match="not mutable"):
        await rag_eval_repo.transition_rag_eval_run(
            run,
            "queued",
            session=db_session,
            **{immutable_field: "tampered"},
        )

    await db_session.refresh(run)
    assert run.configuration_snapshot == original_snapshot
    assert run.configuration_id == configuration.id
    assert run.suite_version == "2026.1"
    assert run.suite_content_hash == "immutable"


@pytest.mark.asyncio
async def test_atomic_finalization_persists_results_and_aggregates_together(db_session):
    configuration = await rag_eval_repo.create_rag_eval_configuration(
        configuration_input(), db_session
    )
    run = await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version="2026.1",
        suite_content_hash="abc",
        total_examples=1,
        session=db_session,
    )
    await rag_eval_repo.claim_next_rag_eval_run(db_session)

    completed = await rag_eval_repo.finalize_rag_eval_run_success(
        run,
        [query_result()],
        overall_metrics={"hit_at_k": 1.0},
        category_metrics={"direct_retrieval": {"hit_at_k": 1.0}},
        resolved_pipeline_snapshot={"pipeline_version": "2"},
        session=db_session,
    )
    rows = list(
        (
            await db_session.exec(
                select(RagEvalQueryResult).where(RagEvalQueryResult.run_id == run.id)
            )
        ).all()
    )

    assert completed.status == "completed"
    assert completed.stage == "finished"
    assert completed.progress == 100.0
    assert completed.overall_metrics == {"hit_at_k": 1.0}
    assert len(rows) == 1
    assert rows[0].faithfulness == 0.9


@pytest.mark.asyncio
async def test_atomic_finalization_rejects_duplicate_examples_before_writes(
    db_session,
):
    configuration = await rag_eval_repo.create_rag_eval_configuration(
        configuration_input(), db_session
    )
    run = await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version="2026.1",
        suite_content_hash="abc",
        total_examples=2,
        session=db_session,
    )
    await rag_eval_repo.claim_next_rag_eval_run(db_session)
    run_id = run.id

    with pytest.raises(ValueError, match="duplicate example_id"):
        await rag_eval_repo.finalize_rag_eval_run_success(
            run,
            [query_result(), query_result()],
            overall_metrics={"hit_at_k": 1.0},
            category_metrics={"direct_retrieval": {"hit_at_k": 1.0}},
            resolved_pipeline_snapshot={"pipeline_version": "2"},
            session=db_session,
        )

    persisted_run = await db_session.get(RagEvalRun, run_id)
    rows = list(
        (
            await db_session.exec(
                select(RagEvalQueryResult).where(RagEvalQueryResult.run_id == run_id)
            )
        ).all()
    )
    assert persisted_run is not None
    assert persisted_run.status == "running"
    assert persisted_run.overall_metrics == {}
    assert persisted_run.category_metrics == {}
    assert rows == []


@pytest.mark.asyncio
async def test_atomic_finalization_rejects_incomplete_buffer_before_writes(db_session):
    configuration = await rag_eval_repo.create_rag_eval_configuration(
        configuration_input(), db_session
    )
    run = await rag_eval_repo.enqueue_rag_eval_run(
        configuration,
        suite_version="2026.1",
        suite_content_hash="abc",
        total_examples=2,
        session=db_session,
    )
    await rag_eval_repo.claim_next_rag_eval_run(db_session)

    with pytest.raises(ValueError, match="exactly 2 query results"):
        await rag_eval_repo.finalize_rag_eval_run_success(
            run,
            [query_result()],
            overall_metrics={"hit_at_k": 1.0},
            category_metrics={},
            resolved_pipeline_snapshot={},
            session=db_session,
        )

    await db_session.refresh(run)
    assert run.status == "running"
    assert await rag_eval_repo.list_rag_eval_query_results(run.id, db_session) == []


@pytest.mark.asyncio
async def test_stale_finalization_cannot_overwrite_failed_run(db_engine):
    async with AsyncSession(db_engine, expire_on_commit=False) as stale_session:
        configuration = await rag_eval_repo.create_rag_eval_configuration(
            configuration_input(), stale_session
        )
        stale_run = await rag_eval_repo.enqueue_rag_eval_run(
            configuration,
            suite_version="2026.1",
            suite_content_hash="race",
            total_examples=1,
            session=stale_session,
        )
        await rag_eval_repo.claim_next_rag_eval_run(stale_session)

        async with AsyncSession(db_engine, expire_on_commit=False) as winner_session:
            winner = await winner_session.get(RagEvalRun, stale_run.id)
            assert winner is not None
            await rag_eval_repo.transition_rag_eval_run(
                winner,
                "failed",
                stage="finished",
                failure_code="winner",
                session=winner_session,
            )

        with pytest.raises(ValueError, match="Only a running evaluation"):
            await rag_eval_repo.finalize_rag_eval_run_success(
                stale_run,
                [query_result()],
                overall_metrics={},
                category_metrics={},
                resolved_pipeline_snapshot={},
                session=stale_session,
            )

        await stale_session.refresh(stale_run)
        assert stale_run.status == "failed"
        assert await rag_eval_repo.list_rag_eval_query_results(
            stale_run.id, stale_session
        ) == []


@pytest.mark.asyncio
async def test_atomic_finalization_refuses_locked_run_with_late_cancellation(
    db_engine,
):
    async with AsyncSession(db_engine, expire_on_commit=False) as stale_session:
        configuration = await rag_eval_repo.create_rag_eval_configuration(
            configuration_input(), stale_session
        )
        stale_run = await rag_eval_repo.enqueue_rag_eval_run(
            configuration,
            suite_version="2026.1",
            suite_content_hash="late-cancel",
            total_examples=1,
            session=stale_session,
        )
        await rag_eval_repo.claim_next_rag_eval_run(stale_session)

        async with AsyncSession(db_engine, expire_on_commit=False) as cancel_session:
            cancelling = await cancel_session.get(RagEvalRun, stale_run.id)
            assert cancelling is not None
            await rag_eval_repo.request_rag_eval_run_cancel(
                cancelling,
                cancel_session,
            )

        with pytest.raises(rag_eval_repo.RagEvalFinalizationCancelled):
            await rag_eval_repo.finalize_rag_eval_run_success(
                stale_run,
                [query_result()],
                overall_metrics={"overall_score": 1.0},
                category_metrics={"direct_retrieval": {"overall_score": 1.0}},
                resolved_pipeline_snapshot={"pipeline_version": "2"},
                session=stale_session,
            )

        await stale_session.refresh(stale_run)
        assert stale_run.status == "running"
        assert stale_run.cancel_requested is True
        assert stale_run.overall_metrics == {}
        assert stale_run.category_metrics == {}
        assert await rag_eval_repo.list_rag_eval_query_results(
            stale_run.id,
            stale_session,
        ) == []


@pytest.mark.parametrize(
    "final_chunks",
    [
        [{"rank": 2, "content": "second", "metadata": {}}],
        [
            {"rank": 1, "content": "first", "metadata": {}},
            {"rank": 1, "content": "duplicate", "metadata": {}},
        ],
        [
            {"rank": 1, "content": "first", "metadata": {}},
            {"rank": 3, "content": "gap", "metadata": {}},
        ],
    ],
)
def test_final_chunks_require_consecutive_unique_ordered_ranks(final_chunks):
    payload = query_result().model_dump(mode="json")
    payload["final_chunks"] = final_chunks

    with pytest.raises(ValidationError, match="consecutive ranks"):
        RagEvalQueryResultCreate.model_validate(payload)


def test_final_chunk_metadata_rejects_non_safe_keys_and_wrong_types():
    payload = query_result().model_dump(mode="json")
    payload["final_chunks"][0]["metadata"] = {
        "source": "support_1.md",
        "private_prompt": "secret",
    }
    with pytest.raises(ValidationError, match="private_prompt"):
        RagEvalQueryResultCreate.model_validate(payload)

    payload["final_chunks"][0]["metadata"] = {"chunk_index": "0"}
    with pytest.raises(ValidationError, match="chunk_index"):
        RagEvalQueryResultCreate.model_validate(payload)


@pytest.mark.parametrize(
    ("ephemeral_field", "value"),
    [
        ("graph_id", 1),
        ("graph_generation", "run-scope"),
        ("raw_document_id", 1),
        ("document_chunk_id", 1),
    ],
)
def test_final_chunk_metadata_rejects_ephemeral_internal_ids(ephemeral_field, value):
    payload = query_result().model_dump(mode="json")
    payload["final_chunks"][0]["metadata"] = {ephemeral_field: value}

    with pytest.raises(ValidationError, match=ephemeral_field):
        RagEvalQueryResultCreate.model_validate(payload)
