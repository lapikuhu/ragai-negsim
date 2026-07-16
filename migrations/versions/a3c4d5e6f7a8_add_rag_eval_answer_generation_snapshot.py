"""add RAG evaluation answer generation snapshot

Revision ID: a3c4d5e6f7a8
Revises: f2b7c8d9e0a1
Create Date: 2026-07-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a3c4d5e6f7a8"
down_revision = "f2b7c8d9e0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ragevalrun",
        sa.Column("answer_generation_model_snapshot", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("ragevalrun", "answer_generation_model_snapshot")
