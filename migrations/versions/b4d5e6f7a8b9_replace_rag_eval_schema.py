"""replace legacy RAG evaluation persistence schema

Revision ID: b4d5e6f7a8b9
Revises: a3c4d5e6f7a8
Create Date: 2026-07-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b4d5e6f7a8b9"
down_revision = "a3c4d5e6f7a8"
branch_labels = None
depends_on = None


STATUS_CHECK = "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')"
STAGE_CHECK = (
    "stage IN ('queued', 'preparing', 'chunking', 'building_index', "
    "'building_graph', 'evaluating', 'scoring', 'cleaning_up', "
    "'persisting', 'finished', 'cleanup_pending')"
)


def upgrade() -> None:
    # No legacy evaluation data needs preservation. Dropping in dependency order
    # avoids carrying transitional profile-based columns into the target schema.
    op.drop_table("ragevalqueryresult")
    op.drop_table("ragevalrun")
    op.drop_table("ragevalpairprofile")

    op.create_table(
        "ragevalconfiguration",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("chunking", sa.JSON(), nullable=False),
        sa.Column("rag", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("last_edit_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["last_edit_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ragevalconfiguration_name"),
        "ragevalconfiguration",
        ["name"],
        unique=True,
    )

    op.create_table(
        "ragevalrun",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("configuration_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("completed_examples", sa.Integer(), nullable=False),
        sa.Column("total_examples", sa.Integer(), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column(
            "cancellation_requested_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("failure_code", sa.String(), nullable=True),
        sa.Column("failure_message", sa.String(), nullable=True),
        sa.Column("configuration_snapshot", sa.JSON(), nullable=False),
        sa.Column("suite_version", sa.String(), nullable=False),
        sa.Column("suite_content_hash", sa.String(), nullable=False),
        sa.Column("resolved_pipeline_snapshot", sa.JSON(), nullable=False),
        sa.Column("overall_metrics", sa.JSON(), nullable=False),
        sa.Column("category_metrics", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            STATUS_CHECK,
            name="ck_rag_eval_run_valid_status",
        ),
        sa.CheckConstraint(
            STAGE_CHECK,
            name="ck_rag_eval_run_valid_stage",
        ),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_rag_eval_run_progress_range",
        ),
        sa.CheckConstraint(
            "completed_examples >= 0 AND total_examples >= 0 "
            "AND completed_examples <= total_examples",
            name="ck_rag_eval_run_example_progress",
        ),
        sa.ForeignKeyConstraint(
            ["configuration_id"],
            ["ragevalconfiguration.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ragevalrun_configuration_id"),
        "ragevalrun",
        ["configuration_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ragevalrun_status"),
        "ragevalrun",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ragevalrun_stage"),
        "ragevalrun",
        ["stage"],
        unique=False,
    )
    op.create_index(
        "ix_rag_eval_run_fifo_queue",
        "ragevalrun",
        ["queued_at", "id"],
        unique=False,
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index(
        "uq_rag_eval_run_global_running",
        "ragevalrun",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )

    op.create_table(
        "ragevalqueryresult",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("example_id", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("answerable", sa.Boolean(), nullable=False),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("reference_answer", sa.String(), nullable=True),
        sa.Column("actual_answer", sa.String(), nullable=False),
        sa.Column("final_chunks", sa.JSON(), nullable=False),
        sa.Column("first_relevant_rank", sa.Integer(), nullable=True),
        sa.Column("hit_at_k", sa.Boolean(), nullable=True),
        sa.Column("mrr_at_k", sa.Float(), nullable=True),
        sa.Column("successful_abstention", sa.Boolean(), nullable=True),
        sa.Column("false_positive_context", sa.Boolean(), nullable=True),
        sa.Column("faithfulness", sa.Float(), nullable=True),
        sa.Column("answer_relevancy", sa.Float(), nullable=True),
        sa.Column("context_precision", sa.Float(), nullable=True),
        sa.Column("context_recall", sa.Float(), nullable=True),
        sa.Column("answer_correctness", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["ragevalrun.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "example_id",
            name="uq_rag_eval_query_result_run_example",
        ),
    )
    op.create_index(
        op.f("ix_ragevalqueryresult_run_id"),
        "ragevalqueryresult",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ragevalqueryresult_example_id"),
        "ragevalqueryresult",
        ["example_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ragevalqueryresult_category"),
        "ragevalqueryresult",
        ["category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("ragevalqueryresult")
    op.drop_table("ragevalrun")
    op.drop_table("ragevalconfiguration")

    op.create_table(
        "ragevalpairprofile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("rag_profile_id", sa.Integer(), nullable=False),
        sa.Column("chunking_profile_id", sa.Integer(), nullable=False),
        sa.Column("retrieval_config", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("last_edit_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chunking_profile_id"], ["chunkingprofile.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["last_edit_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["rag_profile_id"], ["ragprofile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ragevalpairprofile_name"),
        "ragevalpairprofile",
        ["name"],
        unique=True,
    )
    op.create_index(
        op.f("ix_ragevalpairprofile_rag_profile_id"),
        "ragevalpairprofile",
        ["rag_profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ragevalpairprofile_chunking_profile_id"),
        "ragevalpairprofile",
        ["chunking_profile_id"],
        unique=False,
    )

    op.create_table(
        "ragevalrun",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pair_profile_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("failure_detail", sa.String(), nullable=True),
        sa.Column("k", sa.Integer(), nullable=False),
        sa.Column("rag_profile_snapshot", sa.JSON(), nullable=True),
        sa.Column("chunking_profile_snapshot", sa.JSON(), nullable=True),
        sa.Column("retrieval_config_snapshot", sa.JSON(), nullable=False),
        sa.Column("answer_generation_model_snapshot", sa.JSON(), nullable=False),
        sa.Column("evaluation_model_snapshot", sa.JSON(), nullable=True),
        sa.Column("aggregate_hit_rate_at_k", sa.Float(), nullable=True),
        sa.Column("aggregate_mrr_at_k", sa.Float(), nullable=True),
        sa.Column("aggregate_ragas_metrics", sa.JSON(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            STATUS_CHECK,
            name="ck_rag_eval_run_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["pair_profile_id"],
            ["ragevalpairprofile.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ragevalrun_pair_profile_id"),
        "ragevalrun",
        ["pair_profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ragevalrun_status"),
        "ragevalrun",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ragevalrun_stage"),
        "ragevalrun",
        ["stage"],
        unique=False,
    )
    op.create_index(
        "uq_rag_eval_run_active_pair",
        "ragevalrun",
        ["pair_profile_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )

    op.create_table(
        "ragevalqueryresult",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("evaluation_id", sa.String(), nullable=False),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("reference_answer", sa.String(), nullable=True),
        sa.Column("answer", sa.String(), nullable=True),
        sa.Column("retrieved_contexts", sa.JSON(), nullable=True),
        sa.Column("retrieved_evaluation_ids", sa.JSON(), nullable=True),
        sa.Column("reference_rank", sa.Integer(), nullable=True),
        sa.Column("hit_at_k", sa.Boolean(), nullable=False),
        sa.Column("mrr_contribution", sa.Float(), nullable=False),
        sa.Column("ragas_metrics", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["ragevalrun.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ragevalqueryresult_run_id"),
        "ragevalqueryresult",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ragevalqueryresult_evaluation_id"),
        "ragevalqueryresult",
        ["evaluation_id"],
        unique=False,
    )
