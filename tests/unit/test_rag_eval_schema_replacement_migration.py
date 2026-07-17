import importlib.util
from pathlib import Path

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint


def _load_migration():
    path = next(
        Path("migrations/versions").glob("*_replace_rag_eval_schema.py")
    )
    spec = importlib.util.spec_from_file_location(
        "rag_eval_schema_replacement_migration", path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _constraint_columns(constraint):
    bound = [column.name for column in constraint.columns]
    return bound or list(constraint._pending_colargs)


def test_schema_replacement_migration_recreates_target_tables_and_constraints(
    monkeypatch,
):
    migration = _load_migration()
    calls = []
    created_tables = {}
    indexes = []

    monkeypatch.setattr(
        migration.op,
        "drop_table",
        lambda name: calls.append(("drop_table", name)),
    )
    monkeypatch.setattr(
        migration.op,
        "create_table",
        lambda name, *elements: (
            calls.append(("create_table", name)),
            created_tables.setdefault(name, elements),
        )[1],
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

    assert migration.down_revision == "a3c4d5e6f7a8"
    assert calls[:3] == [
        ("drop_table", "ragevalqueryresult"),
        ("drop_table", "ragevalrun"),
        ("drop_table", "ragevalpairprofile"),
    ]
    assert set(created_tables) == {
        "ragevalconfiguration",
        "ragevalrun",
        "ragevalqueryresult",
    }

    config_elements = created_tables["ragevalconfiguration"]
    config_columns = {element.name for element in config_elements if hasattr(element, "name")}
    assert {"name", "chunking", "rag", "metrics"} <= config_columns
    assert "rag_profile_id" not in config_columns
    assert "chunking_profile_id" not in config_columns

    run_elements = created_tables["ragevalrun"]
    run_columns = {element.name for element in run_elements if hasattr(element, "name")}
    assert {
        "configuration_id",
        "configuration_snapshot",
        "suite_version",
        "suite_content_hash",
        "resolved_pipeline_snapshot",
        "overall_metrics",
        "category_metrics",
    } <= run_columns
    assert {
        tuple(fk.target_fullname for fk in constraint.elements)
        for constraint in run_elements
        if isinstance(constraint, ForeignKeyConstraint)
    } == {("ragevalconfiguration.id",)}
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_rag_eval_run_valid_stage"
        and "cleanup_pending" in str(constraint.sqltext)
        for constraint in run_elements
    )

    query_elements = created_tables["ragevalqueryresult"]
    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_rag_eval_query_result_run_example"
        and _constraint_columns(constraint) == ["run_id", "example_id"]
        for constraint in query_elements
    )
    assert any(
        name == "uq_rag_eval_run_global_running"
        and table == "ragevalrun"
        and columns == ["status"]
        and kwargs["unique"] is True
        and str(kwargs["postgresql_where"]) == "status = 'running'"
        for name, table, columns, kwargs in indexes
    )
