"""add rag evaluation persistence

Revision ID: e7a2c9d4f1b6
Revises: d5e8f1a2b3c4
Create Date: 2026-07-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e7a2c9d4f1b6"
down_revision = "d5e8f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ragevalpairprofile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("rag_profile_id", sa.Integer(), nullable=False),
        sa.Column("chunking_profile_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("last_edit_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chunking_profile_id"], ["chunkingprofile.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["last_edit_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["rag_profile_id"], ["ragprofile.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rag_profile_id",
            "chunking_profile_id",
            name="uq_rag_eval_pair_rag_chunking",
        ),
    )
    op.create_index(
        op.f("ix_ragevalpairprofile_chunking_profile_id"),
        "ragevalpairprofile",
        ["chunking_profile_id"],
        unique=False,
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
        sa.Column("evaluation_model_snapshot", sa.JSON(), nullable=True),
        sa.Column("aggregate_hit_rate_at_k", sa.Float(), nullable=True),
        sa.Column("aggregate_mrr_at_k", sa.Float(), nullable=True),
        sa.Column("aggregate_ragas_metrics", sa.JSON(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_rag_eval_run_valid_status",
        ),
        sa.ForeignKeyConstraint(["pair_profile_id"], ["ragevalpairprofile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ragevalrun_pair_profile_id"),
        "ragevalrun",
        ["pair_profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ragevalrun_stage"),
        "ragevalrun",
        ["stage"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ragevalrun_status"),
        "ragevalrun",
        ["status"],
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
        op.f("ix_ragevalqueryresult_evaluation_id"),
        "ragevalqueryresult",
        ["evaluation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ragevalqueryresult_run_id"),
        "ragevalqueryresult",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ragevalqueryresult_run_id"), table_name="ragevalqueryresult")
    op.drop_index(
        op.f("ix_ragevalqueryresult_evaluation_id"), table_name="ragevalqueryresult"
    )
    op.drop_table("ragevalqueryresult")

    op.drop_index("uq_rag_eval_run_active_pair", table_name="ragevalrun")
    op.drop_index(op.f("ix_ragevalrun_status"), table_name="ragevalrun")
    op.drop_index(op.f("ix_ragevalrun_stage"), table_name="ragevalrun")
    op.drop_index(op.f("ix_ragevalrun_pair_profile_id"), table_name="ragevalrun")
    op.drop_table("ragevalrun")

    op.drop_index(
        op.f("ix_ragevalpairprofile_rag_profile_id"), table_name="ragevalpairprofile"
    )
    op.drop_index(
        op.f("ix_ragevalpairprofile_name"), table_name="ragevalpairprofile"
    )
    op.drop_index(
        op.f("ix_ragevalpairprofile_chunking_profile_id"),
        table_name="ragevalpairprofile",
    )
    op.drop_table("ragevalpairprofile")
