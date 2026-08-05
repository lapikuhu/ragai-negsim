import asyncio
import inspect
import threading
import zlib
from datetime import datetime, timezone
from hashlib import sha256
from types import SimpleNamespace

import pytest

from app.schemas.corpus_bm25_indices_schemas import CorpusBm25IndexMetadata


@pytest.mark.asyncio
async def test_list_bm25_indices_forwards_pagination_and_filters(monkeypatch):
    from app.services import corpus_bm25_indices_service

    captured = {}
    expected = [SimpleNamespace(id=17)]

    async def fake_list(session, **filters):
        captured.update(session=session, **filters)
        return expected

    monkeypatch.setattr(
        corpus_bm25_indices_service.corpus_bm25_indices_repo,
        "list_corpus_bm25_index_metadata",
        fake_list,
    )

    result = await corpus_bm25_indices_service.list_corpus_bm25_indices_srvc(
        session="session",
        skip=5,
        limit=10,
        corpus_id=11,
        chunking_profile_id=3,
        status="built",
    )

    assert result is expected
    assert captured == {
        "session": "session",
        "skip": 5,
        "limit": 10,
        "corpus_id": 11,
        "chunking_profile_id": 3,
        "status": "built",
    }


def _chunk(chunk_id: int, content: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=chunk_id,
        raw_document_id=8,
        content=content,
        chunk_metadata={"source": "course.pdf"},
    )


class _Bm25Repository:
    def __init__(self) -> None:
        self.created = []
        self.transitions = []
        self.artifact: bytes | None = None
        self.status = "created"
        self.error: str | None = None

    def metadata(self) -> CorpusBm25IndexMetadata:
        now = datetime.now(timezone.utc)
        return CorpusBm25IndexMetadata(
            id=71,
            name="course lexical index",
            corpus_id=11,
            chunking_profile_id=3,
            status=self.status,
            format_version="pickle-zlib-v1",
            document_count=2,
            document_chunk_ids_checksum=(
                "a194e05c72a3b17a5ca3f0d3b796b7e8a7924ab5b0baf6b6f60f73c3f8b32d1e"
            ),
            compressed_artifact_checksum=(sha256(self.artifact).hexdigest() if self.artifact else None),
            built_at=now if self.status == "built" else None,
            created_at=now,
            last_updated=now,
            build_error=self.error,
        )

    def prepare_corpus_bm25_index(self, index_in):
        return SimpleNamespace(id=None)

    async def create_corpus_bm25_index(
        self,
        index_in,
        session,
        *,
        prepared_index=None,
    ):
        self.created.append(index_in)
        index = prepared_index or SimpleNamespace(id=None)
        index.id = 71
        return index

    async def mark_corpus_bm25_index_building(self, index_id, session):
        assert index_id == 71
        self.transitions.append("building")
        self.status = "building"
        return self.metadata()

    async def mark_corpus_bm25_index_built(self, index_id, *, artifact, document_chunk_ids, session):
        assert index_id == 71
        assert document_chunk_ids == [20, 3]
        self.transitions.append("built")
        self.artifact = artifact
        self.status = "built"
        return self.metadata()

    async def mark_corpus_bm25_index_failed(self, index_id, build_error, session):
        assert index_id == 71
        self.transitions.append("failed")
        self.status = "failed"
        self.error = build_error
        return self.metadata()

    async def mark_corpus_bm25_index_cancelled(self, index_id, build_error, session):
        assert index_id == 71
        if self.status == "built":
            raise ValueError("Invalid corpus BM25 index status transition")
        self.transitions.append("cancelled")
        self.status = "cancelled"
        self.error = build_error
        return self.metadata()

    async def cancel_corpus_bm25_index_build(self, index_id, build_error, session):
        assert index_id == 71
        self.transitions.append("cancelled")
        self.status = "cancelled"
        self.artifact = None
        self.error = build_error
        return self.metadata()

    async def fail_corpus_bm25_index_build(self, index_id, build_error, session):
        assert index_id == 71
        self.transitions.append("failed")
        self.status = "failed"
        self.artifact = None
        self.error = build_error
        return self.metadata()


def _install_repository(monkeypatch, service, repository: _Bm25Repository) -> None:
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "prepare_corpus_bm25_index",
        repository.prepare_corpus_bm25_index,
    )
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "create_corpus_bm25_index",
        repository.create_corpus_bm25_index,
    )
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "mark_corpus_bm25_index_building",
        repository.mark_corpus_bm25_index_building,
    )
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "mark_corpus_bm25_index_built",
        repository.mark_corpus_bm25_index_built,
    )
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "mark_corpus_bm25_index_failed",
        repository.mark_corpus_bm25_index_failed,
    )
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "mark_corpus_bm25_index_cancelled",
        repository.mark_corpus_bm25_index_cancelled,
    )
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "cancel_corpus_bm25_index_build",
        repository.cancel_corpus_bm25_index_build,
        raising=False,
    )
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "fail_corpus_bm25_index_build",
        repository.fail_corpus_bm25_index_build,
        raising=False,
    )


@pytest.mark.asyncio
async def test_builds_validated_bm25_artifact_for_selected_chunk_snapshot(monkeypatch):
    from app.services import corpus_bm25_indices_service as service

    repository = _Bm25Repository()
    _install_repository(monkeypatch, service, repository)
    selected = []
    runner_calls = []

    async def fake_list_chunks(corpus_id, chunking_profile_id, session):
        selected.append((corpus_id, chunking_profile_id, session))
        return [_chunk(20, "payment terms"), _chunk(3, "delivery schedule")]

    async def inline_runner(function, *args, **kwargs):
        runner_calls.append(function)
        return function(*args, **kwargs)

    monkeypatch.setattr(service, "list_corpus_document_chunks_for_profile", fake_list_chunks)

    result = await service.build_corpus_bm25_index_srvc(
        name="course lexical index",
        corpus_id=11,
        chunking_profile_id=3,
        session=object(),
        run_in_thread=inline_runner,
    )

    assert selected[0][:2] == (11, 3)
    assert len(runner_calls) == 1
    assert repository.created[0].document_chunk_ids == [20, 3]
    assert result.status == "built"
    assert result.document_count == 2
    assert result.document_chunk_ids_checksum == (
        "a194e05c72a3b17a5ca3f0d3b796b7e8a7924ab5b0baf6b6f60f73c3f8b32d1e"
    )
    assert not hasattr(result, "artifact")

    retriever = service.load_validated_bm25_artifact(
        repository.artifact,
        expected_checksum=sha256(repository.artifact).hexdigest(),
        format_version="pickle-zlib-v1",
        expected_document_count=2,
    )
    assert len(retriever.docs) == 2
    assert [document.metadata["document_chunk_id"] for document in retriever.docs] == [20, 3]
    assert all(type(document.metadata["document_chunk_id"]) is int for document in retriever.docs)


@pytest.mark.asyncio
async def test_default_thread_runner_builds_and_serializes_off_event_loop(monkeypatch):
    from app.services import corpus_bm25_indices_service as service

    repository = _Bm25Repository()
    _install_repository(monkeypatch, service, repository)
    loop_thread_id = threading.get_ident()
    worker_thread_ids = []
    original_build = service._build_serialize_and_validate_bm25

    async def fake_list_chunks(*_args, **_kwargs):
        return [_chunk(20, "payment terms"), _chunk(3, "delivery schedule")]

    def record_worker_thread(documents):
        worker_thread_ids.append(threading.get_ident())
        return original_build(documents)

    monkeypatch.setattr(service, "list_corpus_document_chunks_for_profile", fake_list_chunks)
    monkeypatch.setattr(
        service,
        "_build_serialize_and_validate_bm25",
        record_worker_thread,
    )

    result = await service.build_corpus_bm25_index_srvc(
        name="course lexical index",
        corpus_id=11,
        chunking_profile_id=3,
        session=object(),
        run_in_thread=asyncio.to_thread,
    )

    assert result.status == "built"
    assert worker_thread_ids
    assert all(worker_thread_id != loop_thread_id for worker_thread_id in worker_thread_ids)


@pytest.mark.asyncio
async def test_empty_chunk_snapshot_fails_before_creating_bm25_row(monkeypatch):
    from app.services import corpus_bm25_indices_service as service

    repository = _Bm25Repository()
    _install_repository(monkeypatch, service, repository)

    async def fake_list_chunks(*_args, **_kwargs):
        return []

    monkeypatch.setattr(service, "list_corpus_document_chunks_for_profile", fake_list_chunks)

    with pytest.raises(ValueError, match="Chunk the corpus first"):
        await service.build_corpus_bm25_index_srvc(
            name="course lexical index",
            corpus_id=11,
            chunking_profile_id=3,
            session=object(),
        )

    assert repository.created == []


@pytest.mark.asyncio
async def test_validation_failure_marks_bm25_failed_without_persisting_an_artifact(monkeypatch):
    from app.services import corpus_bm25_indices_service as service

    repository = _Bm25Repository()
    _install_repository(monkeypatch, service, repository)

    async def fake_list_chunks(*_args, **_kwargs):
        return [_chunk(20, "payment terms"), _chunk(3, "delivery schedule")]

    def reject_artifact(*_args, **_kwargs):
        raise ValueError("artifact cannot be loaded")

    monkeypatch.setattr(service, "list_corpus_document_chunks_for_profile", fake_list_chunks)
    monkeypatch.setattr(service, "load_validated_bm25_artifact", reject_artifact)

    with pytest.raises(ValueError, match="artifact cannot be loaded"):
        await service.build_corpus_bm25_index_srvc(
            name="course lexical index",
            corpus_id=11,
            chunking_profile_id=3,
            session=object(),
            run_in_thread=lambda function, *args, **kwargs: _immediate(function, *args, **kwargs),
        )

    assert repository.transitions == ["building", "failed"]
    assert repository.status == "failed"
    assert repository.artifact is None


async def _immediate(function, *args, **kwargs):
    return function(*args, **kwargs)


@pytest.mark.asyncio
async def test_persistence_failure_marks_bm25_failed_without_usable_artifact(monkeypatch):
    from app.services import corpus_bm25_indices_service as service

    repository = _Bm25Repository()
    _install_repository(monkeypatch, service, repository)

    async def fake_list_chunks(*_args, **_kwargs):
        return [_chunk(20, "payment terms"), _chunk(3, "delivery schedule")]

    async def reject_persistence(*_args, **_kwargs):
        raise RuntimeError("database write failed")

    monkeypatch.setattr(service, "list_corpus_document_chunks_for_profile", fake_list_chunks)
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "mark_corpus_bm25_index_built",
        reject_persistence,
    )

    with pytest.raises(RuntimeError, match="database write failed"):
        await service.build_corpus_bm25_index_srvc(
            name="course lexical index",
            corpus_id=11,
            chunking_profile_id=3,
            session=object(),
            run_in_thread=_immediate,
        )

    assert repository.transitions == ["building", "failed"]
    assert repository.status == "failed"
    assert repository.artifact is None


@pytest.mark.asyncio
async def test_task_cancellation_during_build_marks_cancelled_without_dense_cleanup(monkeypatch):
    from app.services import corpus_bm25_indices_service as service
    from app.airag.vector_stores import vector_stores

    repository = _Bm25Repository()
    _install_repository(monkeypatch, service, repository)
    runner_started = asyncio.Event()

    async def fake_list_chunks(*_args, **_kwargs):
        return [_chunk(20, "payment terms"), _chunk(3, "delivery schedule")]

    async def blocking_runner(*_args, **_kwargs):
        runner_started.set()
        await asyncio.Event().wait()

    async def forbid_dense_vector_deletion(*_args, **_kwargs):
        raise AssertionError("BM25 cancellation must not delete dense vectors")

    monkeypatch.setattr(service, "list_corpus_document_chunks_for_profile", fake_list_chunks)
    monkeypatch.setattr(
        vector_stores,
        "delete_vectors_from_vector_store",
        forbid_dense_vector_deletion,
    )

    task = asyncio.create_task(
        service.build_corpus_bm25_index_srvc(
            name="course lexical index",
            corpus_id=11,
            chunking_profile_id=3,
            session=object(),
            run_in_thread=blocking_runner,
        )
    )
    await runner_started.wait()
    task.cancel("build interrupted")

    with pytest.raises(asyncio.CancelledError, match="build interrupted"):
        await task

    assert repository.transitions == ["building", "cancelled"]
    assert repository.status == "cancelled"
    assert repository.artifact is None


@pytest.mark.asyncio
async def test_task_cancellation_after_create_commit_cleans_created_row(monkeypatch):
    from app.services import corpus_bm25_indices_service as service

    repository = _Bm25Repository()
    _install_repository(monkeypatch, service, repository)
    create_committed = asyncio.Event()
    allow_create_return = asyncio.Event()

    async def fake_list_chunks(*_args, **_kwargs):
        return [_chunk(20, "payment terms"), _chunk(3, "delivery schedule")]

    async def create_then_pause(index_in, session, *, prepared_index=None):
        repository.created.append(index_in)
        repository.status = "created"
        create_committed.set()
        await allow_create_return.wait()
        index = prepared_index or SimpleNamespace(id=None)
        index.id = 71
        return index

    monkeypatch.setattr(service, "list_corpus_document_chunks_for_profile", fake_list_chunks)
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "create_corpus_bm25_index",
        create_then_pause,
    )

    task = asyncio.create_task(
        service.build_corpus_bm25_index_srvc(
            name="course lexical index",
            corpus_id=11,
            chunking_profile_id=3,
            session=object(),
            run_in_thread=_immediate,
        )
    )
    await create_committed.wait()
    task.cancel("cancel after create commit")
    allow_create_return.set()

    with pytest.raises(asyncio.CancelledError, match="cancel after create commit"):
        await task

    assert repository.status == "cancelled"
    assert repository.artifact is None
    assert repository.transitions == ["cancelled"]


@pytest.mark.asyncio
async def test_repeated_task_cancellation_cannot_interrupt_durable_create(monkeypatch):
    from app.services import corpus_bm25_indices_service as service

    repository = _Bm25Repository()
    _install_repository(monkeypatch, service, repository)
    create_committed = asyncio.Event()
    allow_create_return = asyncio.Event()

    async def fake_list_chunks(*_args, **_kwargs):
        return [_chunk(20, "payment terms"), _chunk(3, "delivery schedule")]

    async def create_then_pause(index_in, session, *, prepared_index=None):
        repository.created.append(index_in)
        repository.status = "created"
        create_committed.set()
        await allow_create_return.wait()
        index = prepared_index or SimpleNamespace(id=None)
        index.id = 71
        return index

    monkeypatch.setattr(service, "list_corpus_document_chunks_for_profile", fake_list_chunks)
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "create_corpus_bm25_index",
        create_then_pause,
    )

    task = asyncio.create_task(
        service.build_corpus_bm25_index_srvc(
            name="course lexical index",
            corpus_id=11,
            chunking_profile_id=3,
            session=object(),
            run_in_thread=_immediate,
        )
    )
    await create_committed.wait()
    task.cancel("first create cancellation")
    await asyncio.sleep(0)
    task.cancel("second create cancellation")
    await asyncio.sleep(0)
    allow_create_return.set()

    with pytest.raises(asyncio.CancelledError, match="first create cancellation"):
        await task

    assert repository.status == "cancelled"
    assert repository.artifact is None


@pytest.mark.asyncio
async def test_task_cancellation_after_built_commit_clears_durable_artifact(monkeypatch):
    from app.services import corpus_bm25_indices_service as service

    repository = _Bm25Repository()
    _install_repository(monkeypatch, service, repository)
    built_committed = asyncio.Event()
    allow_built_return = asyncio.Event()

    async def fake_list_chunks(*_args, **_kwargs):
        return [_chunk(20, "payment terms"), _chunk(3, "delivery schedule")]

    async def persist_then_pause(
        index_id,
        *,
        artifact,
        document_chunk_ids,
        session,
    ):
        assert document_chunk_ids == [20, 3]
        repository.transitions.append("built")
        repository.status = "built"
        repository.artifact = artifact
        built_committed.set()
        await allow_built_return.wait()
        return repository.metadata()

    monkeypatch.setattr(service, "list_corpus_document_chunks_for_profile", fake_list_chunks)
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "mark_corpus_bm25_index_built",
        persist_then_pause,
    )

    task = asyncio.create_task(
        service.build_corpus_bm25_index_srvc(
            name="course lexical index",
            corpus_id=11,
            chunking_profile_id=3,
            session=object(),
            run_in_thread=_immediate,
        )
    )
    await built_committed.wait()
    task.cancel("cancel after built commit")
    allow_built_return.set()

    with pytest.raises(asyncio.CancelledError, match="cancel after built commit"):
        await task

    assert repository.transitions == ["building", "built", "cancelled"]
    assert repository.status == "cancelled"
    assert repository.artifact is None


@pytest.mark.asyncio
async def test_repeated_task_cancellation_cannot_interrupt_built_persistence(monkeypatch):
    from app.services import corpus_bm25_indices_service as service

    repository = _Bm25Repository()
    _install_repository(monkeypatch, service, repository)
    built_committed = asyncio.Event()
    allow_built_return = asyncio.Event()
    persistence_settled = False

    async def fake_list_chunks(*_args, **_kwargs):
        return [_chunk(20, "payment terms"), _chunk(3, "delivery schedule")]

    async def persist_then_pause(
        index_id,
        *,
        artifact,
        document_chunk_ids,
        session,
    ):
        nonlocal persistence_settled
        repository.transitions.append("built")
        repository.status = "built"
        repository.artifact = artifact
        built_committed.set()
        await allow_built_return.wait()
        persistence_settled = True
        return repository.metadata()

    monkeypatch.setattr(service, "list_corpus_document_chunks_for_profile", fake_list_chunks)
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "mark_corpus_bm25_index_built",
        persist_then_pause,
    )

    task = asyncio.create_task(
        service.build_corpus_bm25_index_srvc(
            name="course lexical index",
            corpus_id=11,
            chunking_profile_id=3,
            session=object(),
            run_in_thread=_immediate,
        )
    )
    await built_committed.wait()
    task.cancel("first built cancellation")
    await asyncio.sleep(0)
    task.cancel("second built cancellation")
    await asyncio.sleep(0)
    allow_built_return.set()

    with pytest.raises(asyncio.CancelledError, match="first built cancellation"):
        await task

    assert repository.status == "cancelled"
    assert repository.artifact is None
    assert persistence_settled is True


@pytest.mark.asyncio
async def test_repeated_task_cancellation_cannot_interrupt_cancellation_cleanup(monkeypatch):
    from app.services import corpus_bm25_indices_service as service

    repository = _Bm25Repository()
    _install_repository(monkeypatch, service, repository)
    runner_started = asyncio.Event()
    cleanup_started = asyncio.Event()
    allow_cleanup = asyncio.Event()
    cache_clears = []

    async def fake_list_chunks(*_args, **_kwargs):
        return [_chunk(20, "payment terms"), _chunk(3, "delivery schedule")]

    async def blocking_runner(*_args, **_kwargs):
        runner_started.set()
        await asyncio.Event().wait()

    async def cleanup_then_pause(index_id, build_error, session):
        cleanup_started.set()
        await allow_cleanup.wait()
        return await repository.cancel_corpus_bm25_index_build(
            index_id,
            build_error,
            session,
        )

    monkeypatch.setattr(service, "list_corpus_document_chunks_for_profile", fake_list_chunks)
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "cancel_corpus_bm25_index_build",
        cleanup_then_pause,
    )
    monkeypatch.setattr(
        service.simulations_service,
        "clear_negotiation_graph_cache_for_bm25_index",
        lambda index_id, **kwargs: cache_clears.append((index_id, kwargs)) or 1,
    )

    task = asyncio.create_task(
        service.build_corpus_bm25_index_srvc(
            name="course lexical index",
            corpus_id=11,
            chunking_profile_id=3,
            session=object(),
            run_in_thread=blocking_runner,
        )
    )
    await runner_started.wait()
    task.cancel("initial build cancellation")
    await cleanup_started.wait()
    task.cancel("first cleanup cancellation")
    await asyncio.sleep(0)
    task.cancel("second cleanup cancellation")
    await asyncio.sleep(0)
    allow_cleanup.set()

    with pytest.raises(asyncio.CancelledError, match="initial build cancellation"):
        await task

    assert repository.status == "cancelled"
    assert repository.artifact is None
    assert cache_clears == [(71, {})]


def test_bm25_reuse_todo_is_adjacent_to_row_creation():
    from app.services import corpus_bm25_indices_service as service

    source = inspect.getsource(service.build_corpus_bm25_index_srvc)
    lines = [line.strip() for line in source.splitlines()]
    todo_index = lines.index(
        "# TODO: Reuse an existing compatible BM25 artifact instead of rebuilding one for every corpus index."
    )

    assert "create_corpus_bm25_index" in lines[todo_index + 1]


def test_load_validation_normalizes_truncated_pickle_errors():
    from app.services import corpus_bm25_indices_service as service

    truncated_protocol_five_pickle = zlib.compress(b"\x80\x05")

    with pytest.raises(ValueError, match="BM25 artifact cannot be loaded"):
        service.load_validated_bm25_artifact(
            truncated_protocol_five_pickle,
            expected_checksum=sha256(truncated_protocol_five_pickle).hexdigest(),
            format_version="pickle-zlib-v1",
            expected_document_count=2,
        )
