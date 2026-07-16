"""add RAG evaluation retrieval configuration snapshots

Revision ID: f2b7c8d9e0a1
Revises: e7a2c9d4f1b6
Create Date: 2026-07-16 00:00:00.000000
"""

import json
import os

from alembic import op
import sqlalchemy as sa


revision = "f2b7c8d9e0a1"
down_revision = "e7a2c9d4f1b6"
branch_labels = None
depends_on = None


def _default_retrieval_config() -> dict[str, object]:
    return {
        "embedding_model": "text-embedding-3-small",
        "graph_build": {
            "llm_provider": "openai",
            "llm_model": os.getenv("OPEN_AI_DEFAULT_MODEL", "gpt-4o-mini"),
            "max_paths_per_chunk": 10,
        },
    }


def upgrade() -> None:
    default_config = json.dumps(_default_retrieval_config())
    op.add_column(
        "ragevalpairprofile",
        sa.Column("retrieval_config", sa.JSON(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE ragevalpairprofile "
            "SET retrieval_config = CAST(:default_config AS json) "
            "WHERE retrieval_config IS NULL"
        ).bindparams(default_config=default_config)
    )
    op.alter_column("ragevalpairprofile", "retrieval_config", nullable=False)

    op.add_column(
        "ragevalrun",
        sa.Column("retrieval_config_snapshot", sa.JSON(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE ragevalrun AS run "
            "SET retrieval_config_snapshot = pair.retrieval_config "
            "FROM ragevalpairprofile AS pair "
            "WHERE run.pair_profile_id = pair.id "
            "AND run.retrieval_config_snapshot IS NULL"
        )
    )
    op.alter_column("ragevalrun", "retrieval_config_snapshot", nullable=False)

    op.drop_constraint(
        "uq_rag_eval_pair_rag_chunking",
        "ragevalpairprofile",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_rag_eval_pair_rag_chunking",
        "ragevalpairprofile",
        ["rag_profile_id", "chunking_profile_id"],
    )
    op.drop_column("ragevalrun", "retrieval_config_snapshot")
    op.drop_column("ragevalpairprofile", "retrieval_config")
