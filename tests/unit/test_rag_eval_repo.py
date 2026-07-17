from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
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
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


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
async def test_atomic_finalization_rolls_back_all_rows_and_aggregates_on_failure(
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

    with pytest.raises(IntegrityError):
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
