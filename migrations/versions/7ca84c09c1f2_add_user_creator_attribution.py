"""Add user creator attribution.

Revision ID: 7ca84c09c1f2
Revises: 6bf595bd3894
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa


revision = "7ca84c09c1f2"
down_revision = "6bf595bd3894"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_user_created_by_user_id_user",
        "user",
        "user",
        ["created_by_user_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_user_created_by_user_id"),
        "user",
        ["created_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_created_by_user_id"), table_name="user")
    op.drop_constraint("fk_user_created_by_user_id_user", "user", type_="foreignkey")
    op.drop_column("user", "created_by_user_id")
