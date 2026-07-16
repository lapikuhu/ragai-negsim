import importlib.util
from pathlib import Path


def _load_migration():
    path = next(
        Path("migrations/versions").glob("*_add_rag_eval_answer_generation_snapshot.py")
    )
    spec = importlib.util.spec_from_file_location("rag_eval_answer_generation_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_adds_non_nullable_answer_generation_snapshot(monkeypatch):
    migration = _load_migration()
    columns = []
    dropped = []

    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: columns.append((table, column)),
    )
    monkeypatch.setattr(
        migration.op,
        "drop_column",
        lambda table, column: dropped.append((table, column)),
    )

    migration.upgrade()

    assert migration.down_revision == "f2b7c8d9e0a1"
    assert [(table, column.name, column.nullable) for table, column in columns] == [
        ("ragevalrun", "answer_generation_model_snapshot", False)
    ]

    migration.downgrade()

    assert dropped == [("ragevalrun", "answer_generation_model_snapshot")]
