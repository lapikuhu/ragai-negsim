import importlib.util
from pathlib import Path


def _load_migration():
    path = next(Path("migrations/versions").glob("*_add_rag_eval_retrieval_config.py"))
    spec = importlib.util.spec_from_file_location("rag_eval_retrieval_config_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_backfills_retrieval_configuration_and_removes_old_pair_constraint(monkeypatch):
    migration = _load_migration()
    columns = []
    statements = []
    altered = []
    dropped = []

    monkeypatch.setattr(migration.op, "add_column", lambda table, column: columns.append((table, column)))
    monkeypatch.setattr(migration.op, "execute", lambda statement: statements.append(str(statement)))
    monkeypatch.setattr(migration.op, "alter_column", lambda *args, **kwargs: altered.append((args, kwargs)))
    monkeypatch.setattr(migration.op, "drop_constraint", lambda *args, **kwargs: dropped.append((args, kwargs)))

    migration.upgrade()

    assert migration.down_revision == "e7a2c9d4f1b6"
    assert {(table, column.name) for table, column in columns} == {
        ("ragevalpairprofile", "retrieval_config"),
        ("ragevalrun", "retrieval_config_snapshot"),
    }
    assert any("ragevalpairprofile" in statement and "retrieval_config" in statement for statement in statements)
    assert any("ragevalrun" in statement and "retrieval_config_snapshot" in statement for statement in statements)
    assert {(args[0], args[1], kwargs["nullable"]) for args, kwargs in altered} == {
        ("ragevalpairprofile", "retrieval_config", False),
        ("ragevalrun", "retrieval_config_snapshot", False),
    }
    assert dropped == [
        (("uq_rag_eval_pair_rag_chunking", "ragevalpairprofile"), {"type_": "unique"})
    ]
