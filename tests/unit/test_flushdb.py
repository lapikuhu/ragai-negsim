from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlmodel import SQLModel

from scripts import flushdb


class _PostgresConnection:
    def __init__(self) -> None:
        self.executed = []
        self.dialect = SimpleNamespace(
            name="postgresql",
            identifier_preparer=SimpleNamespace(
                format_table=lambda table: f'"{table.name}"'
            ),
        )

    def execute(self, statement) -> None:
        self.executed.append(statement)


def test_drop_model_tables_uses_postgres_cascade(monkeypatch):
    connection = _PostgresConnection()
    drop_all = MagicMock(
        side_effect=AssertionError("PostgreSQL must not use metadata.drop_all")
    )
    monkeypatch.setattr(SQLModel.metadata, "drop_all", drop_all)

    flushdb._drop_model_tables(connection)

    assert len(connection.executed) == 1
    sql = str(connection.executed[0])
    assert sql.startswith("DROP TABLE IF EXISTS ")
    assert sql.endswith(" CASCADE")
    assert '"corpusbm25buildjob"' in sql
    assert '"corpusbm25index"' in sql
    assert '"fullcorpusindexpipejob"' in sql
    assert set(table.name for table in SQLModel.metadata.tables.values()) == {
        identifier.strip('"')
        for identifier in sql.removeprefix("DROP TABLE IF EXISTS ")
        .removesuffix(" CASCADE")
        .split(", ")
    }
    drop_all.assert_not_called()


def test_drop_model_tables_keeps_drop_all_for_other_dialects(monkeypatch):
    connection = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    drop_all = MagicMock()
    monkeypatch.setattr(SQLModel.metadata, "drop_all", drop_all)

    flushdb._drop_model_tables(connection)

    drop_all.assert_called_once_with(connection)
