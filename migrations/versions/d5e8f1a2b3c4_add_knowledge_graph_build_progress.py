"""add knowledge graph build progress

Revision ID: d5e8f1a2b3c4
Revises: 3bbdb71076fd
Create Date: 2026-07-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "d5e8f1a2b3c4"
down_revision = "3bbdb71076fd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledgegraphbuildjob", sa.Column("total_documents", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("knowledgegraphbuildjob", sa.Column("processed_documents", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("knowledgegraphbuildjob", sa.Column("current_raw_document_id", sa.Integer(), nullable=True))
    op.add_column("knowledgegraphbuildjob", sa.Column("current_document_label", sa.String(), nullable=True))
    op.add_column("knowledgegraphbuildjob", sa.Column("node_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("knowledgegraphbuildjob", sa.Column("relationship_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_foreign_key(
        "fk_knowledgegraphbuildjob_current_raw_document_id",
        "knowledgegraphbuildjob",
        "rawdocument",
        ["current_raw_document_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_knowledgegraphbuildjob_current_raw_document_id", "knowledgegraphbuildjob", type_="foreignkey")
    op.drop_column("knowledgegraphbuildjob", "relationship_count")
    op.drop_column("knowledgegraphbuildjob", "node_count")
    op.drop_column("knowledgegraphbuildjob", "current_document_label")
    op.drop_column("knowledgegraphbuildjob", "current_raw_document_id")
    op.drop_column("knowledgegraphbuildjob", "processed_documents")
    op.drop_column("knowledgegraphbuildjob", "total_documents")
