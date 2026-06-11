"""add indexing job cancel requested

Revision ID: 4b7d55dfd1e4
Revises: f1452cd6b1a5
Create Date: 2026-06-11 13:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "4b7d55dfd1e4"
down_revision = "f1452cd6b1a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "indexingjob",
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("indexingjob", "cancel_requested", server_default=None)


def downgrade() -> None:
    op.drop_column("indexingjob", "cancel_requested")
