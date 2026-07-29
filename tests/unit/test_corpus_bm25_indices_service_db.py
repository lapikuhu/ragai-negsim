import asyncio
from hashlib import sha256
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.chunking_profiles import ChunkingProfile  # noqa: F401
from app.models.corpus import Corpus  # noqa: F401
from app.models.corpus_bm25_indices import CorpusBm25Index
from app.models.full_corpus_index_pipe_jobs import FullCorpusIndexPipeJob  # noqa: F401
from app.repositories import corpus_bm25_indices_repo
from app.services import corpus_bm25_indices_service as service


def _chunk(chunk_id: int, content: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=chunk_id,
        raw_document_id=8,
        content=content,
        chunk_metadata={"source": "course.pdf"},
    )


async def _inline_runner(function, *args, **kwargs):
    return function(*args, **kwargs)


@pytest_asyncio.fixture
async def bm25_db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(CorpusBm25Index.__table__.create)
    yield engine
    await engine.dispose()


@pytest.fixture
def selected_chunks(monkeypatch):
    async def fake_list_chunks(corpus_id, chunking_profile_id, session):
        assert (corpus_id, chunking_profile_id) == (11, 3)
        return [_chunk(20, "payment terms"), _chunk(3, "delivery schedule")]

    monkeypatch.setattr(service, "list_corpus_document_chunks_for_profile", fake_list_chunks)


@pytest.mark.asyncio
async def test_database_build_atomically_persists_safe_validated_artifact(
    bm25_db_engine,
    selected_chunks,
):
    async with AsyncSession(bm25_db_engine, expire_on_commit=False) as session:
        result = await service.build_corpus_bm25_index_srvc(
            name="database lexical success",
            corpus_id=11,
            chunking_profile_id=3,
            session=session,
            run_in_thread=_inline_runner,
        )

    assert result.status == "built"
    assert result.document_count == 2
    assert result.document_chunk_ids_checksum == sha256(b"3,20").hexdigest()
    assert not hasattr(result, "artifact")

    async with AsyncSession(bm25_db_engine, expire_on_commit=False) as verify_session:
        metadata = await corpus_bm25_indices_repo.get_corpus_bm25_index_metadata_by_id(
            result.id,
            verify_session,
        )
        artifact = await corpus_bm25_indices_repo.get_corpus_bm25_index_artifact_by_id(
            result.id,
            verify_session,
        )

    assert metadata is not None
    assert metadata.status == "built"
    assert metadata.compressed_artifact_checksum == sha256(artifact).hexdigest()
    assert not hasattr(metadata, "artifact")
    retriever = service.load_validated_bm25_artifact(
        artifact,
        expected_checksum=metadata.compressed_artifact_checksum,
        format_version=metadata.format_version,
        expected_document_count=2,
    )
    assert [document.metadata["document_chunk_id"] for document in retriever.docs] == [20, 3]


@pytest.mark.asyncio
async def test_database_validation_failure_is_failed_without_artifact(
    bm25_db_engine,
    selected_chunks,
    monkeypatch,
):
    def reject_validation(*_args, **_kwargs):
        raise ValueError("database artifact validation failed")

    monkeypatch.setattr(service, "load_validated_bm25_artifact", reject_validation)

    async with AsyncSession(bm25_db_engine, expire_on_commit=False) as session:
        with pytest.raises(ValueError, match="database artifact validation failed"):
            await service.build_corpus_bm25_index_srvc(
                name="database lexical failure",
                corpus_id=11,
                chunking_profile_id=3,
                session=session,
                run_in_thread=_inline_runner,
            )

        metadata = (
            await corpus_bm25_indices_repo.list_corpus_bm25_index_metadata(
                session,
                status="failed",
            )
        )[0]
        artifact = await corpus_bm25_indices_repo.get_corpus_bm25_index_artifact_by_id(
            metadata.id,
            session,
        )

    assert metadata.status == "failed"
    assert artifact is None
    assert metadata.compressed_artifact_checksum is None


@pytest.mark.asyncio
async def test_database_task_cancellation_after_built_commit_clears_artifact(
    bm25_db_engine,
    selected_chunks,
    monkeypatch,
):
    built_committed = asyncio.Event()
    allow_built_return = asyncio.Event()
    original_mark_built = corpus_bm25_indices_repo.mark_corpus_bm25_index_built

    async def persist_then_pause(*args, **kwargs):
        result = await original_mark_built(*args, **kwargs)
        built_committed.set()
        await allow_built_return.wait()
        return result

    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "mark_corpus_bm25_index_built",
        persist_then_pause,
    )

    async with AsyncSession(bm25_db_engine, expire_on_commit=False) as session:
        task = asyncio.create_task(
            service.build_corpus_bm25_index_srvc(
                name="database lexical cancelled",
                corpus_id=11,
                chunking_profile_id=3,
                session=session,
                run_in_thread=_inline_runner,
            )
        )
        await built_committed.wait()
        task.cancel("cancel after database commit")
        allow_built_return.set()

        with pytest.raises(asyncio.CancelledError, match="cancel after database commit"):
            await task

    async with AsyncSession(bm25_db_engine, expire_on_commit=False) as verify_session:
        metadata = (
            await corpus_bm25_indices_repo.list_corpus_bm25_index_metadata(
                verify_session,
            )
        )[0]
        artifact = await corpus_bm25_indices_repo.get_corpus_bm25_index_artifact_by_id(
            metadata.id,
            verify_session,
        )

    assert metadata.status == "cancelled"
    assert metadata.compressed_artifact_checksum is None
    assert metadata.built_at is None
    assert artifact is None


@pytest.mark.asyncio
async def test_database_post_commit_create_exception_is_compensated_to_failed(
    bm25_db_engine,
    selected_chunks,
    monkeypatch,
):
    original_create = corpus_bm25_indices_repo.create_corpus_bm25_index

    async def create_then_raise(*args, **kwargs):
        await original_create(*args, **kwargs)
        raise RuntimeError("create return failed after commit")

    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "create_corpus_bm25_index",
        create_then_raise,
    )

    async with AsyncSession(bm25_db_engine, expire_on_commit=False) as session:
        with pytest.raises(RuntimeError, match="create return failed after commit"):
            await service.build_corpus_bm25_index_srvc(
                name="database create ambiguity",
                corpus_id=11,
                chunking_profile_id=3,
                session=session,
                run_in_thread=_inline_runner,
            )

    async with AsyncSession(bm25_db_engine, expire_on_commit=False) as verify_session:
        metadata = (
            await corpus_bm25_indices_repo.list_corpus_bm25_index_metadata(
                verify_session,
            )
        )[0]
        artifact = await corpus_bm25_indices_repo.get_corpus_bm25_index_artifact_by_id(
            metadata.id,
            verify_session,
        )

    assert metadata.status == "failed"
    assert artifact is None
    assert metadata.compressed_artifact_checksum is None
    assert metadata.built_at is None


@pytest.mark.asyncio
async def test_database_post_commit_built_exception_clears_artifact_and_fails(
    bm25_db_engine,
    selected_chunks,
    monkeypatch,
):
    original_mark_built = corpus_bm25_indices_repo.mark_corpus_bm25_index_built

    async def persist_then_raise(*args, **kwargs):
        await original_mark_built(*args, **kwargs)
        raise RuntimeError("built return failed after commit")

    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "mark_corpus_bm25_index_built",
        persist_then_raise,
    )

    async with AsyncSession(bm25_db_engine, expire_on_commit=False) as session:
        with pytest.raises(RuntimeError, match="built return failed after commit"):
            await service.build_corpus_bm25_index_srvc(
                name="database built ambiguity",
                corpus_id=11,
                chunking_profile_id=3,
                session=session,
                run_in_thread=_inline_runner,
            )

    async with AsyncSession(bm25_db_engine, expire_on_commit=False) as verify_session:
        metadata = (
            await corpus_bm25_indices_repo.list_corpus_bm25_index_metadata(
                verify_session,
            )
        )[0]
        artifact = await corpus_bm25_indices_repo.get_corpus_bm25_index_artifact_by_id(
            metadata.id,
            verify_session,
        )

    assert metadata.status == "failed"
    assert artifact is None
    assert metadata.compressed_artifact_checksum is None
    assert metadata.built_at is None


@pytest.mark.asyncio
async def test_database_repeated_cancellation_cannot_interrupt_failure_cleanup(
    bm25_db_engine,
    selected_chunks,
    monkeypatch,
):
    cleanup_started = asyncio.Event()
    allow_cleanup = asyncio.Event()
    original_mark_failed = corpus_bm25_indices_repo.mark_corpus_bm25_index_failed
    original_compensation = getattr(
        corpus_bm25_indices_repo,
        "fail_corpus_bm25_index_build",
        None,
    )

    def reject_validation(*_args, **_kwargs):
        raise ValueError("validation failed before cleanup")

    async def cleanup_then_pause(*args, **kwargs):
        cleanup_started.set()
        await allow_cleanup.wait()
        operation = original_compensation or original_mark_failed
        return await operation(*args, **kwargs)

    monkeypatch.setattr(service, "load_validated_bm25_artifact", reject_validation)
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "mark_corpus_bm25_index_failed",
        cleanup_then_pause,
    )
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "fail_corpus_bm25_index_build",
        cleanup_then_pause,
        raising=False,
    )

    async with AsyncSession(bm25_db_engine, expire_on_commit=False) as session:
        task = asyncio.create_task(
            service.build_corpus_bm25_index_srvc(
                name="database failure cleanup cancellation",
                corpus_id=11,
                chunking_profile_id=3,
                session=session,
                run_in_thread=_inline_runner,
            )
        )
        await cleanup_started.wait()
        task.cancel("first failure-cleanup cancellation")
        await asyncio.sleep(0)
        task.cancel("second failure-cleanup cancellation")
        await asyncio.sleep(0)
        allow_cleanup.set()

        with pytest.raises(
            asyncio.CancelledError,
            match="first failure-cleanup cancellation",
        ):
            await task

    async with AsyncSession(bm25_db_engine, expire_on_commit=False) as verify_session:
        metadata = (
            await corpus_bm25_indices_repo.list_corpus_bm25_index_metadata(
                verify_session,
            )
        )[0]
        artifact = await corpus_bm25_indices_repo.get_corpus_bm25_index_artifact_by_id(
            metadata.id,
            verify_session,
        )

    assert metadata.status == "failed"
    assert artifact is None
    assert metadata.compressed_artifact_checksum is None
    assert metadata.built_at is None
