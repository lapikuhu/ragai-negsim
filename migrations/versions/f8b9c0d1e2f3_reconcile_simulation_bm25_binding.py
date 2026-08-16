"""Reconcile simulation dense and BM25 index bindings.

Revision ID: f8b9c0d1e2f3
Revises: e7a8b9c0d1e2
"""

from alembic import op
import sqlalchemy as sa


revision = "f8b9c0d1e2f3"
down_revision = "e7a8b9c0d1e2"
branch_labels = None
depends_on = None


def _columns(inspector: sa.Inspector) -> dict[str, dict]:
    return {
        column["name"]: column
        for column in inspector.get_columns("simulation")
    }


def _foreign_keys_for_column(
    inspector: sa.Inspector,
    column_name: str,
) -> list[dict]:
    return [
        foreign_key
        for foreign_key in inspector.get_foreign_keys("simulation")
        if foreign_key["constrained_columns"] == [column_name]
    ]


def _reconcile_bm25_indexes(inspector: sa.Inspector) -> None:
    for constraint in inspector.get_unique_constraints("corpusbm25index"):
        if constraint["column_names"] == ["name"]:
            op.drop_constraint(
                constraint["name"],
                "corpusbm25index",
                type_="unique",
            )

    indexes = {
        index["name"]: index
        for index in inspector.get_indexes("corpusbm25index")
    }
    name_index = indexes.get("ix_corpusbm25index_name")
    if name_index is not None and not name_index["unique"]:
        op.drop_index(
            "ix_corpusbm25index_name",
            table_name="corpusbm25index",
        )
        name_index = None
    if name_index is None:
        op.create_index(
            "ix_corpusbm25index_name",
            "corpusbm25index",
            ["name"],
            unique=True,
        )

    if "ix_corpusbm25index_created_by_bm25_build_job_id" in indexes:
        op.drop_index(
            "ix_corpusbm25index_created_by_bm25_build_job_id",
            table_name="corpusbm25index",
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = _columns(inspector)

    if "bm25_index_id" not in columns:
        op.add_column(
            "simulation",
            sa.Column("bm25_index_id", sa.Integer(), nullable=True),
        )
    elif not columns["bm25_index_id"]["nullable"]:
        op.alter_column(
            "simulation",
            "bm25_index_id",
            existing_type=sa.Integer(),
            nullable=True,
        )

    bm25_foreign_keys = _foreign_keys_for_column(inspector, "bm25_index_id")
    has_expected_bm25_foreign_key = any(
        foreign_key["referred_table"] == "corpusbm25index"
        and foreign_key["referred_columns"] == ["id"]
        for foreign_key in bm25_foreign_keys
    )
    if not has_expected_bm25_foreign_key:
        for foreign_key in bm25_foreign_keys:
            op.drop_constraint(
                foreign_key["name"],
                "simulation",
                type_="foreignkey",
            )
        op.create_foreign_key(
            "fk_simulation_bm25_index",
            "simulation",
            "corpusbm25index",
            ["bm25_index_id"],
            ["id"],
        )

    if not columns["corpus_index_id"]["nullable"]:
        op.alter_column(
            "simulation",
            "corpus_index_id",
            existing_type=sa.Integer(),
            nullable=True,
        )

    _reconcile_bm25_indexes(inspector)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = _columns(inspector)

    if "bm25_index_id" in columns:
        for foreign_key in _foreign_keys_for_column(inspector, "bm25_index_id"):
            op.drop_constraint(
                foreign_key["name"],
                "simulation",
                type_="foreignkey",
            )
        op.drop_column("simulation", "bm25_index_id")

    if columns["corpus_index_id"]["nullable"]:
        op.alter_column(
            "simulation",
            "corpus_index_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

    indexes = {
        index["name"]: index
        for index in inspector.get_indexes("corpusbm25index")
    }
    name_index = indexes.get("ix_corpusbm25index_name")
    if name_index is not None and name_index["unique"]:
        op.drop_index(
            "ix_corpusbm25index_name",
            table_name="corpusbm25index",
        )
        op.create_index(
            "ix_corpusbm25index_name",
            "corpusbm25index",
            ["name"],
        )
    op.create_unique_constraint(
        "corpusbm25index_name_key",
        "corpusbm25index",
        ["name"],
    )
    if "ix_corpusbm25index_created_by_bm25_build_job_id" not in indexes:
        op.create_index(
            "ix_corpusbm25index_created_by_bm25_build_job_id",
            "corpusbm25index",
            ["created_by_bm25_build_job_id"],
        )
