from datetime import datetime, timezone
from hashlib import sha256
from types import SimpleNamespace

import pytest
from sqlalchemy import CheckConstraint
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable

try:
    from app.models.corpus_bm25_indices import CorpusBm25Index
    from app.repositories import corpus_bm25_indices_repo
    from app.schemas.corpus_bm25_indices_schemas import CorpusBm25IndexCreate
except ModuleNotFoundError:
    CorpusBm25Index = None
    corpus_bm25_indices_repo = None
    CorpusBm25IndexCreate = None


def _require_bm25_persistence() -> None:
    assert CorpusBm25Index is not None, "CorpusBm25Index persistence model is missing"
    assert corpus_bm25_indices_repo is not None, "BM25 persistence repository is missing"
    assert CorpusBm25IndexCreate is not None, "BM25 persistence DTOs are missing"


def _metadata_row(index: CorpusBm25Index, *, status: str | None = None):
    return SimpleNamespace(
        _mapping={
            "id": index.id,
            "name": index.name,
            "corpus_id": index.corpus_id,
            "chunking_profile_id": index.chunking_profile_id,
            "corpus_chunk_set_id": index.corpus_chunk_set_id,
            "corpus_chunk_set_revision": index.corpus_chunk_set_revision,
            "corpus_chunk_set_checksum": index.corpus_chunk_set_checksum,
            "status": status or index.status,
            "format_version": index.format_version,
            "document_count": index.document_count,
            "document_chunk_ids_checksum": index.document_chunk_ids_checksum,
            "compressed_artifact_checksum": index.compressed_artifact_checksum,
            "built_at": index.built_at,
            "created_at": index.created_at,
            "last_updated": index.last_updated,
            "build_error": index.build_error,
            "created_by_full_corpus_index_pipe_job_id": index.created_by_full_corpus_index_pipe_job_id,
            "created_by_bm25_build_job_id": index.created_by_bm25_build_job_id,
        }
    )


def test_bm25_artifact_table_has_required_postgres_schema_and_safe_defaults():
    _require_bm25_persistence()
    table = CorpusBm25Index.__table__

    assert {
        "id",
        "name",
        "corpus_id",
        "chunking_profile_id",
        "corpus_chunk_set_id",
        "corpus_chunk_set_revision",
        "corpus_chunk_set_checksum",
        "status",
        "format_version",
        "artifact",
        "document_count",
        "document_chunk_ids_checksum",
        "compressed_artifact_checksum",
        "built_at",
        "created_at",
        "last_updated",
        "build_error",
        "created_by_full_corpus_index_pipe_job_id",
        "created_by_bm25_build_job_id",
    } <= set(table.c.keys())
    assert table.c.name.unique is True
    assert table.c.artifact.nullable is True
    assert str(table.c.format_version.server_default.arg) == "'pickle-zlib-v1'"
    assert str(table.c.status.server_default.arg) == "'created'"

    foreign_keys = {foreign_key.target_fullname for foreign_key in table.foreign_keys}
    assert foreign_keys == {
        "corpus.id",
        "chunkingprofile.id",
        "corpuschunkset.id",
        "fullcorpusindexpipejob.id",
        "corpusbm25buildjob.id",
    }
    status_constraint = next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_corpus_bm25_index_valid_status"
    )
    assert "'created'" in str(status_constraint.sqltext)
    assert "'retired'" in str(status_constraint.sqltext)

    ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
    assert "artifact BYTEA" in ddl
    assert "DEFAULT 'pickle-zlib-v1'" in ddl

    sqlite_ddl = str(CreateTable(table).compile(dialect=sqlite.dialect()))
    assert "artifact BLOB" in sqlite_ddl


def test_canonical_chunk_checksum_sorts_ids_and_covers_single_and_empty_sets():
    _require_bm25_persistence()

    assert corpus_bm25_indices_repo.document_chunk_ids_checksum([19, 2, 11]) == (
        "8d07d17ff08d8d86c287ed16f39ad962457ccdb24b290ba0bc9340d2249d7151"
    )
    assert corpus_bm25_indices_repo.document_chunk_ids_checksum([42]) == (
        "73475cb40a568e8da8a045ced110137e159f890ac4da883b6b17dc651b3a8049"
    )
    assert corpus_bm25_indices_repo.document_chunk_ids_checksum([]) == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_metadata_dto_and_statement_never_materialize_artifact_bytes():
    _require_bm25_persistence()
    metadata = corpus_bm25_indices_repo.CorpusBm25IndexMetadata(
        id=3,
        name="bm25 candidate",
        corpus_id=5,
        chunking_profile_id=7,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="c" * 64,
        status="built",
        format_version="pickle-zlib-v1",
        document_count=2,
        document_chunk_ids_checksum="a" * 64,
        compressed_artifact_checksum="b" * 64,
        built_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
        created_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
        last_updated=datetime(2026, 7, 28, tzinfo=timezone.utc),
        build_error=None,
        created_by_full_corpus_index_pipe_job_id=None,
        created_by_bm25_build_job_id=None,
    )

    assert "artifact" not in metadata.model_dump()
    assert metadata.corpus_chunk_set_id == 21
    assert metadata.corpus_chunk_set_revision == 3
    assert metadata.corpus_chunk_set_checksum == "c" * 64
    statement = corpus_bm25_indices_repo._corpus_bm25_index_metadata_statement().where(
        CorpusBm25Index.id == 3
    )
    assert "artifact" not in statement.selected_columns.keys()
    assert {
        "corpus_chunk_set_id",
        "corpus_chunk_set_revision",
        "corpus_chunk_set_checksum",
    } <= set(statement.selected_columns.keys())

    model = CorpusBm25Index(
        id=3,
        name="bm25 candidate",
        corpus_id=5,
        chunking_profile_id=7,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="c" * 64,
        document_chunk_ids_checksum="a" * 64,
        artifact=b"private-binary",
    )
    assert "artifact" not in model.model_dump()


@pytest.mark.asyncio
async def test_metadata_list_is_deterministically_paginated_after_filtering():
    _require_bm25_persistence()

    class FakeResult:
        def all(self):
            return []

    class RecordingSession:
        statement = None

        async def exec(self, statement):
            self.statement = statement
            return FakeResult()

    session = RecordingSession()

    result = await corpus_bm25_indices_repo.list_corpus_bm25_index_metadata(
        session,
        skip=5,
        limit=10,
        corpus_id=11,
        chunking_profile_id=3,
        status="built",
    )

    assert result == []
    assert session.statement._offset_clause.value == 5
    assert session.statement._limit_clause.value == 10
    assert list(session.statement._order_by_clauses) == [CorpusBm25Index.id]


@pytest.mark.asyncio
async def test_built_simulation_candidates_are_unpaginated_and_metadata_only():
    _require_bm25_persistence()

    class FakeResult:
        def all(self):
            return []

    class RecordingSession:
        statement = None

        async def exec(self, statement):
            self.statement = statement
            return FakeResult()

    session = RecordingSession()

    result = (
        await corpus_bm25_indices_repo.list_built_corpus_bm25_index_metadata_for_corpus(
            44,
            session,
        )
    )

    assert result == []
    statement = session.statement
    assert statement._limit_clause is None
    assert statement._offset_clause is None
    assert list(statement._order_by_clauses) == [CorpusBm25Index.id]
    assert "artifact" not in statement.selected_columns.keys()
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "corpusbm25index.corpus_id" in sql
    assert "corpusbm25index.status" in sql


@pytest.mark.asyncio
async def test_metadata_lookup_by_name_is_exact_and_does_not_select_artifact_bytes():
    _require_bm25_persistence()
    index = CorpusBm25Index(
        id=14,
        name="policy lexical",
        corpus_id=5,
        chunking_profile_id=7,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="c" * 64,
        status="built",
        document_chunk_ids_checksum="a" * 64,
    )

    class FakeResult:
        def first(self):
            return _metadata_row(index)

    class RecordingSession:
        statement = None

        async def exec(self, statement):
            self.statement = statement
            return FakeResult()

    lookup = getattr(
        corpus_bm25_indices_repo,
        "get_corpus_bm25_index_metadata_by_name",
        None,
    )
    assert lookup is not None
    session = RecordingSession()

    result = await lookup("policy lexical", session)

    assert result.id == 14
    assert result.corpus_chunk_set_id == 21
    assert result.corpus_chunk_set_revision == 3
    assert result.corpus_chunk_set_checksum == "c" * 64
    assert "artifact" not in session.statement.selected_columns.keys()
    compiled = session.statement.compile(dialect=postgresql.dialect())
    assert compiled.params == {"name_1": "policy lexical", "param_1": 1}


@pytest.mark.asyncio
async def test_metadata_lookup_by_full_pipe_owner_is_safe():
    _require_bm25_persistence()
    index = CorpusBm25Index(
        id=15,
        name="owned lexical",
        corpus_id=5,
        chunking_profile_id=7,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="c" * 64,
        status="built",
        document_chunk_ids_checksum="a" * 64,
        created_by_full_corpus_index_pipe_job_id=81,
    )

    class FakeResult:
        def first(self):
            return _metadata_row(index)

    class RecordingSession:
        statement = None

        async def exec(self, statement):
            self.statement = statement
            return FakeResult()

    lookup = getattr(
        corpus_bm25_indices_repo,
        "get_corpus_bm25_index_metadata_by_full_pipe_job_id",
        None,
    )
    assert lookup is not None
    session = RecordingSession()

    result = await lookup(81, session)

    assert result.id == 15
    assert result.corpus_chunk_set_id == 21
    assert "artifact" not in session.statement.selected_columns.keys()


@pytest.mark.asyncio
async def test_link_bm25_index_to_full_pipe_owner_is_persisted():
    _require_bm25_persistence()

    class FakeResult:
        def one_or_none(self):
            return 15

    class RecordingSession:
        statement = None
        commits = 0

        async def exec(self, statement):
            self.statement = statement
            return FakeResult()

        async def commit(self):
            self.commits += 1

    linker = getattr(
        corpus_bm25_indices_repo,
        "link_corpus_bm25_index_to_full_pipe_job",
        None,
    )
    assert linker is not None
    session = RecordingSession()

    await linker(15, 81, session)

    assert session.statement.is_update
    assert session.commits == 1


@pytest.mark.asyncio
async def test_stale_lifecycle_object_cannot_overwrite_current_status(monkeypatch):
    _require_bm25_persistence()
    stale_index = CorpusBm25Index(
        id=9,
        name="bm25 candidate",
        corpus_id=5,
        chunking_profile_id=7,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="c" * 64,
        status="building",
        document_chunk_ids_checksum="a" * 64,
    )
    current_index = CorpusBm25Index(
        id=9,
        name="bm25 candidate",
        corpus_id=5,
        chunking_profile_id=7,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="c" * 64,
        status="cancelled",
        document_chunk_ids_checksum="a" * 64,
    )

    class FakeResult:
        def __init__(self, row):
            self.row = row

        def one_or_none(self):
            return self.row

        def first(self):
            return self.row

    class LockingSession:
        statement = None
        rollback_calls = 0
        commit_calls = 0
        exec_calls = 0

        async def exec(self, statement):
            self.statement = statement
            self.exec_calls += 1
            return FakeResult(None if self.exec_calls == 1 else _metadata_row(current_index))

        async def rollback(self):
            self.rollback_calls += 1

        async def commit(self):
            self.commit_calls += 1

    session = LockingSession()

    with pytest.raises(ValueError, match="Invalid corpus BM25 index status transition"):
        await corpus_bm25_indices_repo.mark_corpus_bm25_index_built(
            stale_index.id,
            artifact=b"later",
            document_chunk_ids=[1],
            session=session,
        )

    assert session.exec_calls == 2
    assert session.rollback_calls == 2
    assert session.commit_calls == 0
    assert current_index.status == "cancelled"


@pytest.mark.asyncio
async def test_successful_lifecycle_update_returns_safe_metadata_without_artifact(monkeypatch):
    _require_bm25_persistence()
    current_index = CorpusBm25Index(
        id=12,
        name="bm25 candidate",
        corpus_id=5,
        chunking_profile_id=7,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="c" * 64,
        status="building",
        document_chunk_ids_checksum="a" * 64,
    )

    class FakeResult:
        def one_or_none(self):
            return _metadata_row(current_index, status="built")

    class RecordingSession:
        statement = None
        commit_calls = 0

        async def exec(self, statement):
            self.statement = statement
            return FakeResult()

        async def commit(self):
            self.commit_calls += 1
    session = RecordingSession()
    result = await corpus_bm25_indices_repo.mark_corpus_bm25_index_built(
        current_index.id,
        artifact=b"binary",
        document_chunk_ids=[1],
        session=session,
    )

    assert isinstance(result, corpus_bm25_indices_repo.CorpusBm25IndexMetadata)
    assert session.statement.is_update
    assert CorpusBm25Index.artifact not in session.statement._returning
    assert CorpusBm25Index.corpus_chunk_set_id in session.statement._returning
    assert CorpusBm25Index.corpus_chunk_set_revision in session.statement._returning
    assert CorpusBm25Index.corpus_chunk_set_checksum in session.statement._returning
    assert session.commit_calls == 1


@pytest.mark.asyncio
async def test_lifecycle_execution_failure_rolls_back_session():
    _require_bm25_persistence()

    class FailingSession:
        rollback_calls = 0

        async def exec(self, _statement):
            raise RuntimeError("database write failed")

        async def rollback(self):
            self.rollback_calls += 1

    session = FailingSession()

    with pytest.raises(RuntimeError, match="database write failed"):
        await corpus_bm25_indices_repo.mark_corpus_bm25_index_building(9, session)

    assert session.rollback_calls == 1


@pytest.mark.asyncio
async def test_delete_execution_failure_rolls_back_session():
    _require_bm25_persistence()

    class FailingSession:
        rollback_calls = 0

        async def exec(self, _statement):
            raise RuntimeError("database delete failed")

        async def rollback(self):
            self.rollback_calls += 1

    session = FailingSession()

    with pytest.raises(RuntimeError, match="database delete failed"):
        await corpus_bm25_indices_repo.delete_corpus_bm25_index(9, session)

    assert session.rollback_calls == 1


@pytest.mark.asyncio
async def test_lifecycle_rejects_an_unpersisted_bm25_index_before_querying():
    _require_bm25_persistence()
    unpersisted = CorpusBm25Index(
        name="bm25 candidate",
        corpus_id=5,
        chunking_profile_id=7,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="c" * 64,
        document_chunk_ids_checksum="a" * 64,
    )

    with pytest.raises(ValueError, match="must be persisted before transition"):
        await corpus_bm25_indices_repo.mark_corpus_bm25_index_building(
            unpersisted,
            object(),
        )


@pytest.mark.asyncio
async def test_create_derives_chunk_snapshot_integrity_from_raw_chunk_ids(monkeypatch):
    _require_bm25_persistence()

    async def fake_commit_and_refresh(_session, index):
        return index

    monkeypatch.setattr(corpus_bm25_indices_repo, "commit_and_refresh", fake_commit_and_refresh)
    created = await corpus_bm25_indices_repo.create_corpus_bm25_index(
        CorpusBm25IndexCreate(
            name="bm25 candidate",
            corpus_id=5,
            chunking_profile_id=7,
            corpus_chunk_set_id=21,
            corpus_chunk_set_revision=3,
            corpus_chunk_set_checksum="c" * 64,
            document_chunk_ids=[19, 2, 11],
        ),
        object(),
    )

    assert created.document_count == 3
    assert created.corpus_chunk_set_id == 21
    assert created.corpus_chunk_set_revision == 3
    assert created.corpus_chunk_set_checksum == "c" * 64
    assert created.document_chunk_ids_checksum == (
        "8d07d17ff08d8d86c287ed16f39ad962457ccdb24b290ba0bc9340d2249d7151"
    )


def test_same_bm25_lifecycle_status_is_not_an_implicit_idempotent_transition():
    _require_bm25_persistence()

    with pytest.raises(ValueError, match="Invalid corpus BM25 index status transition"):
        corpus_bm25_indices_repo.ensure_corpus_bm25_index_status_transition(
            "created", "created"
        )


@pytest.mark.asyncio
async def test_lifecycle_transitions_are_independent_from_dense_index_status(monkeypatch):
    _require_bm25_persistence()
    index = CorpusBm25Index(
        id=10,
        name="bm25 candidate",
        corpus_id=5,
        chunking_profile_id=7,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="c" * 64,
        document_chunk_ids_checksum="a" * 64,
    )

    class FakeResult:
        def __init__(self, status):
            self.status = status

        def one_or_none(self):
            return _metadata_row(index, status=self.status)

    class LockingSession:
        statuses = iter(["building", "built", "retired"])
        commit_calls = 0

        async def exec(self, _statement):
            return FakeResult(next(self.statuses))

        async def commit(self):
            self.commit_calls += 1

    session = LockingSession()

    building = await corpus_bm25_indices_repo.mark_corpus_bm25_index_building(index.id, session)
    built = await corpus_bm25_indices_repo.mark_corpus_bm25_index_built(
        index.id,
        artifact=b"compressed-index",
        document_chunk_ids=[19, 2],
        session=session,
    )
    retired = await corpus_bm25_indices_repo.mark_corpus_bm25_index_retired(index.id, session)

    assert [building.status, built.status, retired.status] == ["building", "built", "retired"]
    assert session.commit_calls == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_status", ["failed", "cancelled"])
async def test_failure_and_cancellation_are_terminal_bm25_lifecycle_states(monkeypatch, terminal_status):
    _require_bm25_persistence()
    index = CorpusBm25Index(
        id=11,
        name=f"bm25 {terminal_status}",
        corpus_id=5,
        chunking_profile_id=7,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="c" * 64,
        document_chunk_ids_checksum="a" * 64,
    )

    class FakeResult:
        def __init__(self, row):
            self.row = row

        def one_or_none(self):
            return self.row

        def first(self):
            return self.row

    class LockingSession:
        calls = 0
        rollback_calls = 0

        async def exec(self, _statement):
            self.calls += 1
            return FakeResult(_metadata_row(index, status=terminal_status) if self.calls != 2 else None)

        async def commit(self):
            pass

        async def rollback(self):
            self.rollback_calls += 1

    session = LockingSession()
    if terminal_status == "failed":
        await corpus_bm25_indices_repo.mark_corpus_bm25_index_failed(index.id, "broken", session)
    else:
        await corpus_bm25_indices_repo.mark_corpus_bm25_index_cancelled(index.id, "stopped", session)

    with pytest.raises(ValueError, match="Invalid corpus BM25 index status transition"):
        await corpus_bm25_indices_repo.mark_corpus_bm25_index_built(
            index.id,
            artifact=b"later",
            document_chunk_ids=[],
            session=session,
        )
