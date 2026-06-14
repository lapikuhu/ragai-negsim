"""add knowledge graph rag

Revision ID: 8c2b19e0cdb1
Revises: 165f7ed30e76
Create Date: 2026-06-14
"""

from alembic import op
import sqlalchemy as sa


revision = "8c2b19e0cdb1"
down_revision = "165f7ed30e76"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledgegraphindex",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("corpus_index_id", sa.Integer(), nullable=False),
        sa.Column("build_config", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("active_generation", sa.String(), nullable=True),
        sa.Column("latest_build_error", sa.String(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("built_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["corpus_index_id"], ["corpusindex.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        op.f("ix_knowledgegraphindex_corpus_index_id"),
        "knowledgegraphindex",
        ["corpus_index_id"],
    )
    op.create_index(
        op.f("ix_knowledgegraphindex_status"),
        "knowledgegraphindex",
        ["status"],
    )
    op.create_index(
        op.f("ix_knowledgegraphindex_active_generation"),
        "knowledgegraphindex",
        ["active_generation"],
    )
    op.create_table(
        "knowledgegraphbuildjob",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("knowledge_graph_index_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("build_config_snapshot", sa.JSON(), nullable=False),
        sa.Column("chunk_ids_snapshot", sa.JSON(), nullable=False),
        sa.Column("candidate_generation", sa.String(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("processed_chunks", sa.Integer(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("failure_detail", sa.String(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["knowledge_graph_index_id"],
            ["knowledgegraphindex.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledgegraphbuildjob_knowledge_graph_index_id"),
        "knowledgegraphbuildjob",
        ["knowledge_graph_index_id"],
    )
    op.create_index(
        op.f("ix_knowledgegraphbuildjob_status"),
        "knowledgegraphbuildjob",
        ["status"],
    )
    op.create_index(
        op.f("ix_knowledgegraphbuildjob_stage"),
        "knowledgegraphbuildjob",
        ["stage"],
    )
    op.create_index(
        op.f("ix_knowledgegraphbuildjob_candidate_generation"),
        "knowledgegraphbuildjob",
        ["candidate_generation"],
    )
    op.add_column(
        "ragprofile",
        sa.Column("knowledge_graph_index_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ragprofile_knowledge_graph_index_id",
        "ragprofile",
        "knowledgegraphindex",
        ["knowledge_graph_index_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_ragprofile_knowledge_graph_index_id"),
        "ragprofile",
        ["knowledge_graph_index_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ragprofile_knowledge_graph_index_id"),
        table_name="ragprofile",
    )
    op.drop_constraint(
        "fk_ragprofile_knowledge_graph_index_id",
        "ragprofile",
        type_="foreignkey",
    )
    op.drop_column("ragprofile", "knowledge_graph_index_id")
    op.drop_table("knowledgegraphbuildjob")
    op.drop_table("knowledgegraphindex")
