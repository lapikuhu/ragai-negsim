"""Add durable corpus BM25 build jobs.

Revision ID: c5e6f7a8b9c0
Revises: 1743d16c7437
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "c5e6f7a8b9c0"
down_revision = "1743d16c7437"
branch_labels = None
depends_on = None


def _create_bm25_artifact_table_if_missing() -> None:
    if "corpusbm25index" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "corpusbm25index",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("corpus_id", sa.Integer(), sa.ForeignKey("corpus.id"), nullable=False),
        sa.Column("chunking_profile_id", sa.Integer(), sa.ForeignKey("chunkingprofile.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="created"),
        sa.Column("format_version", sa.String(), nullable=False, server_default="pickle-zlib-v1"),
        sa.Column("artifact", sa.LargeBinary(), nullable=True),
        sa.Column("document_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("document_chunk_ids_checksum", sa.String(64), nullable=False),
        sa.Column("compressed_artifact_checksum", sa.String(64), nullable=True),
        sa.Column("built_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("build_error", sa.String(), nullable=True),
        sa.Column("created_by_full_corpus_index_pipe_job_id", sa.Integer(), sa.ForeignKey("fullcorpusindexpipejob.id"), nullable=True),
        sa.CheckConstraint(
            "status IN ('created', 'building', 'built', 'failed', 'cancelled', 'retired')",
            name="ck_corpus_bm25_index_valid_status",
        ),
    )
    op.create_index("ix_corpusbm25index_name", "corpusbm25index", ["name"])
    op.create_index("ix_corpusbm25index_corpus_id", "corpusbm25index", ["corpus_id"])
    op.create_index("ix_corpusbm25index_chunking_profile_id", "corpusbm25index", ["chunking_profile_id"])
    op.create_index("ix_corpusbm25index_status", "corpusbm25index", ["status"])


def upgrade() -> None:
    _create_bm25_artifact_table_if_missing()
    op.create_table(
        "corpusbm25buildjob",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requested_artifact_name", sa.String(), nullable=False),
        sa.Column("corpus_id", sa.Integer(), sa.ForeignKey("corpus.id"), nullable=False),
        sa.Column("chunking_profile_id", sa.Integer(), sa.ForeignKey("chunkingprofile.id"), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("document_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("document_chunk_ids_checksum", sa.String(64), nullable=False),
        sa.Column("distinct_document_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(), nullable=False, server_default="queued"),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_bm25_index_id", sa.Integer(), sa.ForeignKey("corpusbm25index.id"), nullable=True),
        sa.Column("failure_detail", sa.String(), nullable=True),
        sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed', 'cancelled')", name="ck_corpus_bm25_build_job_valid_status"),
        sa.CheckConstraint("stage IN ('queued', 'validating_snapshot', 'building_artifact', 'persisting_artifact', 'finished')", name="ck_corpus_bm25_build_job_valid_stage"),
    )
    op.create_index("ix_corpusbm25buildjob_corpus_id", "corpusbm25buildjob", ["corpus_id"])
    op.create_index("ix_corpusbm25buildjob_chunking_profile_id", "corpusbm25buildjob", ["chunking_profile_id"])
    op.create_index("ix_corpusbm25buildjob_status", "corpusbm25buildjob", ["status"])
    op.create_index("ix_corpusbm25buildjob_stage", "corpusbm25buildjob", ["stage"])
    op.add_column("corpusbm25index", sa.Column("created_by_bm25_build_job_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_corpusbm25index_created_by_bm25_build_job", "corpusbm25index", "corpusbm25buildjob", ["created_by_bm25_build_job_id"], ["id"])
    op.create_index("ix_corpusbm25index_created_by_bm25_build_job_id", "corpusbm25index", ["created_by_bm25_build_job_id"])


def downgrade() -> None:
    op.drop_index("ix_corpusbm25index_created_by_bm25_build_job_id", table_name="corpusbm25index")
    op.drop_constraint("fk_corpusbm25index_created_by_bm25_build_job", "corpusbm25index", type_="foreignkey")
    op.drop_column("corpusbm25index", "created_by_bm25_build_job_id")
    op.drop_table("corpusbm25buildjob")
