import importlib.util
from pathlib import Path

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint


def _load_rag_eval_migration():
    path = next(Path("migrations/versions").glob("*_add_rag_eval_persistence.py"))
    spec = importlib.util.spec_from_file_location("rag_eval_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rag_eval_migration_declares_schema_and_postgres_active_run_index(monkeypatch):
    migration = _load_rag_eval_migration()
    created_tables = {}
    indexes = []

    monkeypatch.setattr(
        migration.op,
        "create_table",
        lambda name, *elements: created_tables.setdefault(name, elements),
    )
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda name, table, columns, **kwargs: indexes.append(
            (name, table, columns, kwargs)
        ),
    )
    monkeypatch.setattr(migration.op, "f", lambda name: name)

    migration.upgrade()

    def constraint_column_names(constraint):
        """Read standalone constraints before Alembic binds them to a table."""
        bound_columns = [column.name for column in constraint.columns]
        return bound_columns or list(constraint._pending_colargs)

    assert migration.down_revision == "d5e8f1a2b3c4"
    assert set(created_tables) == {
        "ragevalpairprofile",
        "ragevalrun",
        "ragevalqueryresult",
    }
    pair_elements = created_tables["ragevalpairprofile"]
    pair_columns = {
        element.name for element in pair_elements if hasattr(element, "name")
    }
    assert {
        "name",
        "rag_profile_id",
        "chunking_profile_id",
        "created_by_user_id",
        "last_edit_by_user_id",
    } <= pair_columns
    pair_foreign_keys = sorted(
        tuple(foreign_key.target_fullname for foreign_key in constraint.elements)
        for constraint in pair_elements
        if isinstance(constraint, ForeignKeyConstraint)
    )
    assert pair_foreign_keys == [
        ("chunkingprofile.id",),
        ("ragprofile.id",),
        ("user.id",),
        ("user.id",),
    ]
    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_rag_eval_pair_rag_chunking"
        and constraint_column_names(constraint)
        == ["rag_profile_id", "chunking_profile_id"]
        for constraint in pair_elements
    )

    run_elements = created_tables["ragevalrun"]
    run_columns = {element.name for element in run_elements if hasattr(element, "name")}
    assert {
        "pair_profile_id",
        "status",
        "stage",
        "cancel_requested",
        "k",
        "rag_profile_snapshot",
        "chunking_profile_snapshot",
        "evaluation_model_snapshot",
        "aggregate_hit_rate_at_k",
        "aggregate_mrr_at_k",
        "aggregate_ragas_metrics",
    } <= run_columns
    assert {
        tuple(foreign_key.target_fullname for foreign_key in constraint.elements)
        for constraint in run_elements
        if isinstance(constraint, ForeignKeyConstraint)
    } == {("ragevalpairprofile.id",)}
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_rag_eval_run_valid_status"
        and str(constraint.sqltext)
        == "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')"
        for constraint in run_elements
    )

    query_result_elements = created_tables["ragevalqueryresult"]
    query_result_columns = {
        element.name for element in query_result_elements if hasattr(element, "name")
    }
    assert {
        "run_id",
        "evaluation_id",
        "query",
        "reference_answer",
        "answer",
        "retrieved_contexts",
        "retrieved_evaluation_ids",
        "reference_rank",
        "hit_at_k",
        "mrr_contribution",
        "ragas_metrics",
    } <= query_result_columns
    assert {
        tuple(foreign_key.target_fullname for foreign_key in constraint.elements)
        for constraint in query_result_elements
        if isinstance(constraint, ForeignKeyConstraint)
    } == {("ragevalrun.id",)}
    assert any(
        name == "ix_ragevalpairprofile_name"
        and table == "ragevalpairprofile"
        and columns == ["name"]
        and kwargs["unique"] is True
        for name, table, columns, kwargs in indexes
    )
    assert any(
        name == "uq_rag_eval_run_active_pair"
        and table == "ragevalrun"
        and columns == ["pair_profile_id"]
        and kwargs["unique"] is True
        and str(kwargs["postgresql_where"]) == "status IN ('queued', 'running')"
        for name, table, columns, kwargs in indexes
    )
