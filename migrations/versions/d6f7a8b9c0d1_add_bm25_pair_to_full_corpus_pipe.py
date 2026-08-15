"""Add BM25 pair orchestration to full corpus pipeline jobs.

Revision ID: d6f7a8b9c0d1
Revises: c5e6f7a8b9c0
"""

from alembic import op
import sqlalchemy as sa


revision = "d6f7a8b9c0d1"
down_revision = "c5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fullcorpusindexpipejob",
        sa.Column(
            "build_bm25",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "fullcorpusindexpipejob",
        sa.Column("requested_bm25_index_name", sa.String(), nullable=True),
    )
    op.add_column(
        "fullcorpusindexpipejob",
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "fullcorpusindexpipejob",
        sa.Column("bm25_build_job_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_full_pipe_requested_by_user",
        "fullcorpusindexpipejob",
        "user",
        ["requested_by_user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_full_pipe_bm25_build_job",
        "fullcorpusindexpipejob",
        "corpusbm25buildjob",
        ["bm25_build_job_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_full_pipe_bm25_build_job",
        "fullcorpusindexpipejob",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_full_pipe_requested_by_user",
        "fullcorpusindexpipejob",
        type_="foreignkey",
    )
    op.drop_column("fullcorpusindexpipejob", "bm25_build_job_id")
    op.drop_column("fullcorpusindexpipejob", "requested_by_user_id")
    op.drop_column("fullcorpusindexpipejob", "requested_bm25_index_name")
    op.drop_column("fullcorpusindexpipejob", "build_bm25")
