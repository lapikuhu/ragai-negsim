"""Persist named corpus chunk sets and artifact build identity.

Revision ID: e7a8b9c0d1e2
Revises: d6f7a8b9c0d1
"""

from alembic import op
import sqlalchemy as sa


revision = "e7a8b9c0d1e2"
down_revision = "d6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "corpuschunkset",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("corpus_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("chunking_profile_id", sa.Integer(), nullable=True),
        sa.Column("chunking_profile_name", sa.String(), nullable=False),
        sa.Column("chunking_strategy", sa.String(), nullable=False),
        sa.Column("chunking_config", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("document_chunk_ids_checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision >= 1", name="ck_corpus_chunk_set_revision_positive"),
        sa.ForeignKeyConstraint(
            ["chunking_profile_id"], ["chunkingprofile.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["corpus_id"], ["corpus.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("corpus_id", "name", name="uq_corpus_chunk_set_corpus_name"),
    )
    op.create_index("ix_corpuschunkset_corpus_id", "corpuschunkset", ["corpus_id"])
    op.create_index(
        "ix_corpuschunkset_chunking_profile_id",
        "corpuschunkset",
        ["chunking_profile_id"],
    )
    op.create_table(
        "corpuschunksetdocumentchunklink",
        sa.Column("corpus_chunk_set_id", sa.Integer(), nullable=False),
        sa.Column("document_chunk_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["corpus_chunk_set_id"], ["corpuschunkset.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["document_chunk_id"], ["documentchunk.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("corpus_chunk_set_id", "document_chunk_id"),
    )

    for table_name in ("corpusindex", "corpusbm25index"):
        op.add_column(table_name, sa.Column("corpus_chunk_set_id", sa.Integer(), nullable=False))
        op.add_column(table_name, sa.Column("corpus_chunk_set_revision", sa.Integer(), nullable=False))
        op.add_column(
            table_name,
            sa.Column("corpus_chunk_set_checksum", sa.String(length=64), nullable=False),
        )
        op.create_index(
            f"ix_{table_name}_corpus_chunk_set_id",
            table_name,
            ["corpus_chunk_set_id"],
        )
        op.create_foreign_key(
            f"fk_{table_name}_corpus_chunk_set",
            table_name,
            "corpuschunkset",
            ["corpus_chunk_set_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    op.add_column(
        "corpusbm25buildjob",
        sa.Column("corpus_chunk_set_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "corpusbm25buildjob",
        sa.Column("corpus_chunk_set_revision", sa.Integer(), nullable=False),
    )
    op.add_column(
        "corpusbm25buildjob",
        sa.Column("corpus_chunk_set_checksum", sa.String(length=64), nullable=False),
    )
    op.create_index(
        "ix_corpusbm25buildjob_corpus_chunk_set_id",
        "corpusbm25buildjob",
        ["corpus_chunk_set_id"],
    )
    op.create_foreign_key(
        "fk_corpusbm25buildjob_corpus_chunk_set",
        "corpusbm25buildjob",
        "corpuschunkset",
        ["corpus_chunk_set_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "fullcorpusindexpipejob",
        sa.Column("requested_chunk_set_name", sa.String(), nullable=False),
    )
    op.add_column(
        "fullcorpusindexpipejob",
        sa.Column("corpus_chunk_set_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_fullcorpusindexpipejob_corpus_chunk_set_id",
        "fullcorpusindexpipejob",
        ["corpus_chunk_set_id"],
    )
    op.create_foreign_key(
        "fk_fullcorpusindexpipejob_corpus_chunk_set",
        "fullcorpusindexpipejob",
        "corpuschunkset",
        ["corpus_chunk_set_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_fullcorpusindexpipejob_corpus_chunk_set",
        "fullcorpusindexpipejob",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_fullcorpusindexpipejob_corpus_chunk_set_id",
        table_name="fullcorpusindexpipejob",
    )
    op.drop_column("fullcorpusindexpipejob", "corpus_chunk_set_id")
    op.drop_column("fullcorpusindexpipejob", "requested_chunk_set_name")

    op.drop_constraint(
        "fk_corpusbm25buildjob_corpus_chunk_set",
        "corpusbm25buildjob",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_corpusbm25buildjob_corpus_chunk_set_id",
        table_name="corpusbm25buildjob",
    )
    op.drop_column("corpusbm25buildjob", "corpus_chunk_set_checksum")
    op.drop_column("corpusbm25buildjob", "corpus_chunk_set_revision")
    op.drop_column("corpusbm25buildjob", "corpus_chunk_set_id")

    for table_name in ("corpusbm25index", "corpusindex"):
        op.drop_constraint(
            f"fk_{table_name}_corpus_chunk_set", table_name, type_="foreignkey"
        )
        op.drop_index(f"ix_{table_name}_corpus_chunk_set_id", table_name=table_name)
        op.drop_column(table_name, "corpus_chunk_set_checksum")
        op.drop_column(table_name, "corpus_chunk_set_revision")
        op.drop_column(table_name, "corpus_chunk_set_id")

    op.drop_table("corpuschunksetdocumentchunklink")
    op.drop_index("ix_corpuschunkset_chunking_profile_id", table_name="corpuschunkset")
    op.drop_index("ix_corpuschunkset_corpus_id", table_name="corpuschunkset")
    op.drop_table("corpuschunkset")
