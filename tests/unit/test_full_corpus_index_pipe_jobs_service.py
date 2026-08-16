import asyncio
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.schemas.full_corpus_index_pipe_jobs_schemas import FullCorpusIndexPipeJobCreate
from app.services import full_corpus_index_pipe_job


def _job(**overrides):
    values = {
        "id": 9,
        "corpus_id": 1,
        "chunking_profile_id": 2,
        "vector_store_id": 3,
        "embedding_model": "mini-l6-v2",
        "requested_index_name": "policy-index",
        "requested_chunk_set_name": "August policy set",
        "requested_vector_namespace": None,
        "build_bm25": False,
        "requested_bm25_index_name": None,
        "requested_by_user_id": 5,
        "bm25_build_job_id": None,
        "corpus_chunk_set_id": None,
        "status": "queued",
        "stage": "validating",
        "current_raw_document_id": None,
        "current_document_name": None,
        "total_documents": 0,
        "processed_documents": 0,
        "chunks_created": 0,
        "chunks_indexed": 0,
        "queued_at": datetime.now(timezone.utc),
        "started_at": None,
        "completed_at": None,
        "candidate_corpus_index_id": None,
        "replaced_corpus_index_id": None,
        "failure_detail": None,
        "cancel_requested": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _chunk_set_snapshot(**overrides):
    chunk_set_values = {
        "id": 21,
        "corpus_id": 1,
        "name": "August policy set",
        "chunking_profile_id": 2,
        "revision": 3,
        "document_chunk_ids_checksum": "a" * 64,
    }
    document_chunk_ids = overrides.pop("document_chunk_ids", [10, 11])
    chunk_set_values.update(overrides)
    return SimpleNamespace(
        chunk_set=SimpleNamespace(**chunk_set_values),
        document_chunk_ids=document_chunk_ids,
    )


@pytest.mark.asyncio
async def test_create_dense_candidate_copies_chunk_set_identity(monkeypatch):
    job = _job(status="running")
    snapshot = _chunk_set_snapshot()
    captured = {}
    candidate = SimpleNamespace(id=88)

    async def create_index(request, _session, **_kwargs):
        captured["request"] = request
        return candidate

    async def set_metadata(index, namespace, _session, **_kwargs):
        assert index is candidate
        assert namespace == "corpus-index-88"
        return index

    class Session:
        def add(self, instance):
            assert instance is job

        async def commit(self):
            return None

        async def refresh(self, instance):
            assert instance is job

    monkeypatch.setattr(
        full_corpus_index_pipe_job,
        "choose_embedding_model",
        lambda _model: (object(), {"dimensionality": 384}),
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job.corpus_indices_repo,
        "create_corpus_index",
        create_index,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job.corpus_indices_repo,
        "set_corpus_index_build_metadata",
        set_metadata,
    )

    result = await full_corpus_index_pipe_job._create_candidate_index(
        job,
        snapshot,
        Session(),
    )

    assert result is candidate
    assert captured["request"].corpus_chunk_set_id == 21
    assert captured["request"].corpus_chunk_set_revision == 3
    assert captured["request"].corpus_chunk_set_checksum == "a" * 64
    assert job.candidate_corpus_index_id == 88


@pytest.mark.asyncio
async def test_queue_bm25_child_uses_existing_job_factory_and_wakes_coordinator(monkeypatch):
    job = _job(
        build_bm25=True,
        requested_bm25_index_name="policy lexical",
        requested_by_user_id=23,
        corpus_chunk_set_id=21,
    )
    queued_child = SimpleNamespace(id=71, status="queued")
    captured = {}

    async def queue_child(
        request,
        requester_id,
        session,
        *,
        reserved_by_full_pipe_job_id,
    ):
        captured["request"] = request
        captured["requester_id"] = requester_id
        captured["session"] = session
        captured["reserved_by_full_pipe_job_id"] = reserved_by_full_pipe_job_id
        return queued_child

    async def link_child(parent, child_id, session):
        parent.bm25_build_job_id = child_id
        parent.stage = "building_bm25"
        return parent

    wake_calls = []
    monkeypatch.setattr(
        full_corpus_index_pipe_job,
        "queue_corpus_bm25_build_job_for_requester_id_srvc",
        queue_child,
        raising=False,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo,
        "set_full_corpus_index_pipe_job_bm25_child",
        link_child,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job,
        "wake_corpus_bm25_build_coordinator",
        lambda: wake_calls.append("wake"),
        raising=False,
    )
    queue_bm25 = getattr(full_corpus_index_pipe_job, "_queue_bm25_child", None)

    assert queue_bm25 is not None
    result = await queue_bm25(job, object())

    assert result is queued_child
    assert captured["request"].requested_artifact_name == "policy lexical"
    assert captured["request"].corpus_chunk_set_id == 21
    assert captured["requester_id"] == 23
    assert captured["reserved_by_full_pipe_job_id"] == 9
    assert job.bm25_build_job_id == 71
    assert wake_calls == ["wake"]


@pytest.mark.asyncio
async def test_wait_for_bm25_child_waits_for_terminal_child_after_parent_cancel(monkeypatch):
    job = _job(bm25_build_job_id=71)
    child_states = iter(
        [
            SimpleNamespace(id=71, status="queued"),
            SimpleNamespace(id=71, status="cancelled"),
        ]
    )
    cancel_calls = []
    sessions = []

    class PollSession:
        async def __aenter__(self):
            sessions.append(self)
            return self

        async def __aexit__(self, *_args):
            return False

    async def get_parent(*_args):
        return SimpleNamespace(cancel_requested=True)

    async def cancel_child(child_id, _session):
        cancel_calls.append(child_id)

    async def get_child(*_args):
        return next(child_states)

    monkeypatch.setattr(
        full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo,
        "get_full_corpus_index_pipe_job_by_id",
        get_parent,
    )
    monkeypatch.setattr(full_corpus_index_pipe_job, "cancel_corpus_bm25_build_job_srvc", cancel_child)
    monkeypatch.setattr(full_corpus_index_pipe_job, "get_corpus_bm25_build_job_srvc", get_child)
    monkeypatch.setattr(full_corpus_index_pipe_job.asyncio, "sleep", AsyncMock())

    with pytest.raises(asyncio.CancelledError):
        await full_corpus_index_pipe_job._wait_for_bm25_child(
            job,
            session_factory=PollSession,
            poll_interval_seconds=0,
        )

    assert cancel_calls == [71]
    assert len(sessions) == 2


@pytest.mark.asyncio
async def test_pair_sanity_check_delegates_to_canonical_hybrid_rule(monkeypatch):
    snapshot = _chunk_set_snapshot()
    job = _job(
        build_bm25=True,
        bm25_build_job_id=71,
        corpus_chunk_set_id=snapshot.chunk_set.id,
    )
    dense = SimpleNamespace(
        id=88,
        status="built",
        name="policy-index",
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="a" * 64,
    )
    child = SimpleNamespace(result_bm25_index_id=202)
    bm25 = SimpleNamespace(
        id=202,
        status="built",
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="a" * 64,
    )
    captured = {}
    bm25_repository = getattr(
        full_corpus_index_pipe_job,
        "corpus_bm25_indices_repo",
        None,
    )
    compatibility_service = getattr(
        full_corpus_index_pipe_job,
        "simulation_retrieval_options_service",
        None,
    )

    assert bm25_repository is not None
    assert compatibility_service is not None
    monkeypatch.setattr(
        bm25_repository,
        "get_corpus_bm25_index_metadata_by_id",
        AsyncMock(return_value=bm25),
        raising=False,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job.corpus_indices_repo,
        "get_corpus_index_document_chunk_ids",
        AsyncMock(return_value=[10, 11]),
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job,
        "get_corpus_chunk_set_snapshot_srvc",
        AsyncMock(return_value=snapshot),
    )

    def ensure_compatible(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        compatibility_service,
        "ensure_hybrid_indices_compatible",
        ensure_compatible,
        raising=False,
    )
    sanity_check = getattr(
        full_corpus_index_pipe_job,
        "_ensure_parent_pair_compatible",
        None,
    )

    assert sanity_check is not None
    await sanity_check(job, dense, child, object())

    assert captured == {
        "corpus_id": 1,
        "corpus_index": dense,
        "bm25_index": bm25,
        "dense_chunk_ids": [10, 11],
        "corpus_chunk_set": snapshot.chunk_set,
    }


@pytest.mark.asyncio
async def test_combined_run_builds_bm25_before_dense_and_checks_pair_before_activation(
    monkeypatch,
    recording_async_session_factory,
):
    job = _job(
        status="running",
        build_bm25=True,
        requested_bm25_index_name="policy lexical",
    )
    snapshot = _chunk_set_snapshot()
    dense = SimpleNamespace(
        id=88,
        status="building",
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="a" * 64,
    )
    child = SimpleNamespace(id=71, status="completed", result_bm25_index_id=202)
    calls = []
    bm25_repository = getattr(
        full_corpus_index_pipe_job,
        "corpus_bm25_indices_repo",
        None,
    )

    assert bm25_repository is not None

    async def get_job(*_args):
        return job

    async def process(current_job, _session):
        assert current_job is job
        calls.append("parse-and-chunk")
        return SimpleNamespace(successful_documents=1, chunks_created=2)

    async def create_chunk_set(current_job, _session):
        assert current_job is job
        current_job.corpus_chunk_set_id = snapshot.chunk_set.id
        calls.append("create-chunk-set")
        return snapshot

    async def create_candidate(current_job, current_snapshot, _session):
        assert current_job is job
        assert current_snapshot is snapshot
        calls.append("create-dense-candidate")
        return dense

    async def queue_child(current_job, _session):
        assert current_job.corpus_chunk_set_id == snapshot.chunk_set.id
        calls.append("queue-bm25")
        return child

    async def wait_child(*_args):
        calls.append("wait-bm25")
        return child

    async def link_owner(*_args):
        calls.append("link-bm25-owner")

    async def embed(current_job, candidate, current_snapshot, _session):
        assert current_job is job
        assert candidate is dense
        assert current_snapshot is snapshot
        calls.append("embed-dense")

    async def check(*_args):
        calls.append("check-compatible")

    async def reload_dense(index_id, _session):
        assert index_id == dense.id
        calls.append("reload-dense")
        return dense

    async def reload_set(chunk_set_id, _session):
        assert chunk_set_id == snapshot.chunk_set.id
        return snapshot

    async def activate(*_args):
        calls.append("activate-dense")
        return SimpleNamespace(candidate_corpus_index_id=88, replaced_corpus_index_id=None)

    async def complete(current, _session, **_kwargs):
        current.status = "completed"
        return current

    async def read_detail(current, _session):
        return current

    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "get_full_corpus_index_pipe_job_by_id", get_job)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_process_documents", process)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_create_job_chunk_set", create_chunk_set)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_create_candidate_index", create_candidate)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_queue_bm25_child", queue_child, raising=False)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_wait_for_bm25_child", wait_child, raising=False)
    monkeypatch.setattr(bm25_repository, "link_corpus_bm25_index_to_full_pipe_job", link_owner, raising=False)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_embed_candidate", embed)
    monkeypatch.setattr(
        full_corpus_index_pipe_job.corpus_indices_repo,
        "get_corpus_index_by_id",
        reload_dense,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job,
        "get_corpus_chunk_set_snapshot_srvc",
        reload_set,
    )
    monkeypatch.setattr(full_corpus_index_pipe_job, "_ensure_parent_pair_compatible", check, raising=False)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_activate_candidate_index", activate)
    async def no_warnings(*_args):
        return []

    async def no_cleanup(*_args):
        return None

    monkeypatch.setattr(full_corpus_index_pipe_job, "_cleanup_retired_index", no_cleanup)
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "list_full_corpus_index_pipe_job_warnings", no_warnings)
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "mark_full_corpus_index_pipe_job_completed", complete)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_read_job_detail", read_detail)
    monkeypatch.setattr(full_corpus_index_pipe_job, "AsyncSessionLocal", recording_async_session_factory)

    result = await full_corpus_index_pipe_job.run_full_corpus_index_pipe_job_srvc(9)

    assert result.status == "completed"
    assert calls == [
        "parse-and-chunk",
        "create-chunk-set",
        "create-dense-candidate",
        "queue-bm25",
        "wait-bm25",
        "link-bm25-owner",
        "embed-dense",
        "reload-dense",
        "check-compatible",
        "activate-dense",
    ]


@pytest.mark.asyncio
async def test_parent_artifact_rollback_removes_pair_set_and_only_unreferenced_chunks(
    monkeypatch,
):
    job = _job(
        status="running",
        stage="embedding",
        bm25_build_job_id=71,
        corpus_chunk_set_id=21,
    )
    dense = SimpleNamespace(id=88, status="building")
    calls = []

    async def mark_rolling_back(current, detail, _session):
        calls.append("mark-parent-rolling-back")
        current.stage = "rolling_back"
        current.failure_detail = detail
        return current

    async def rollback_bm25(**kwargs):
        calls.append(
            "delete-bm25-artifact"
            if kwargs.get("delete_artifact")
            else "terminalize-child"
        )
        return SimpleNamespace(status="failed")

    async def list_owned_chunks(parent_id, _session):
        assert parent_id == 9
        return [SimpleNamespace(id=11), SimpleNamespace(id=12)]

    async def list_indexed_chunks(*_args, **_kwargs):
        return []

    async def delete_indexed_chunks(index_id, _session):
        assert index_id == 88

    async def delete_dense(candidate, _session):
        assert candidate is dense
        calls.append("delete-dense-vectors-and-index")

    async def delete_set(chunk_set_id, owner_job_id, _session):
        assert (chunk_set_id, owner_job_id) == (21, 9)
        calls.append("delete-set-links-and-set")
        return [11]

    async def delete_unreferenced_chunks(**kwargs):
        assert kwargs["full_corpus_index_pipe_job_id"] == 9
        assert kwargs["document_chunk_ids"] == [11]
        calls.append("delete-unreferenced-job-chunks")
        return 1

    async def fail_parent(current, detail, _session):
        calls.append("mark-parent-failed")
        current.status = "failed"
        current.failure_detail = detail
        return current

    async def read_detail(current, _session):
        return current

    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "mark_full_corpus_index_pipe_job_rolling_back", mark_rolling_back, raising=False)
    monkeypatch.setattr(full_corpus_index_pipe_job, "rollback_parent_owned_corpus_bm25_job_srvc", rollback_bm25, raising=False)
    monkeypatch.setattr(full_corpus_index_pipe_job.document_chunks_repo, "list_document_chunks_for_job", list_owned_chunks)
    monkeypatch.setattr(full_corpus_index_pipe_job.indexed_chunks_repo, "get_indexed_chunks_by_corpus_index_id", list_indexed_chunks)
    monkeypatch.setattr(full_corpus_index_pipe_job.indexed_chunks_repo, "delete_indexed_chunks_by_corpus_index_id_force", delete_indexed_chunks)
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_indices_repo, "delete_corpus_index", delete_dense)
    monkeypatch.setattr(full_corpus_index_pipe_job, "delete_owned_corpus_chunk_set_srvc", delete_set)
    monkeypatch.setattr(full_corpus_index_pipe_job.document_chunks_repo, "delete_unreferenced_job_document_chunks_by_ids", delete_unreferenced_chunks)
    monkeypatch.setattr(
        full_corpus_index_pipe_job.simulations_service,
        "clear_negotiation_graph_cache_for_corpus_index",
        lambda _index_id: None,
    )
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "mark_full_corpus_index_pipe_job_failed", fail_parent)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_read_job_detail", read_detail)
    rollback = getattr(full_corpus_index_pipe_job, "_rollback_parent_artifacts", None)

    assert rollback is not None
    result = await rollback(
        job,
        dense,
        terminal_status="failed",
        detail="dense index build failed: boom",
        session=object(),
    )

    assert result.status == "failed"
    assert calls == [
        "mark-parent-rolling-back",
        "terminalize-child",
        "delete-dense-vectors-and-index",
        "delete-bm25-artifact",
        "delete-set-links-and-set",
        "delete-unreferenced-job-chunks",
        "mark-parent-failed",
    ]


@pytest.mark.asyncio
async def test_failure_compensates_dense_candidate_already_marked_built(monkeypatch):
    job = _job(status="running")
    dense = SimpleNamespace(id=88, status="built", name="policy-index")
    compensate = AsyncMock(side_effect=lambda index, detail, _session: index)
    failed_parent = AsyncMock(side_effect=lambda current, detail, _session: current)

    monkeypatch.setattr(
        full_corpus_index_pipe_job.corpus_indices_repo,
        "fail_corpus_index_build",
        compensate,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo,
        "mark_full_corpus_index_pipe_job_failed",
        failed_parent,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job,
        "_read_job_detail",
        AsyncMock(return_value=job),
    )

    session = object()
    await full_corpus_index_pipe_job._fail_job_and_candidate(
        job,
        dense,
        session,
        "compatibility failed",
    )

    compensate.assert_awaited_once_with(dense, "compatibility failed", session)
    assert dense.name == "policy-index [candidate job 9]"


@pytest.mark.asyncio
async def test_parent_stays_rolling_back_while_running_child_cancellation_is_pending(monkeypatch):
    job = _job(status="running", stage="embedding", bm25_build_job_id=71)
    dense = SimpleNamespace(id=88, status="building")

    async def mark_rolling_back(current, detail, _session):
        current.stage = "rolling_back"
        return current

    monkeypatch.setattr(
        full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo,
        "mark_full_corpus_index_pipe_job_rolling_back",
        mark_rolling_back,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job,
        "rollback_parent_owned_corpus_bm25_job_srvc",
        AsyncMock(return_value=SimpleNamespace(status="running")),
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job.document_chunks_repo,
        "list_document_chunks_for_job",
        AsyncMock(return_value=[]),
    )
    fail_parent = AsyncMock()
    monkeypatch.setattr(
        full_corpus_index_pipe_job,
        "_fail_job_and_candidate",
        fail_parent,
    )

    with pytest.raises(RuntimeError, match="cancellation is still pending"):
        await full_corpus_index_pipe_job._rollback_parent_artifacts(
            job,
            dense,
            terminal_status="failed",
            detail="interrupted",
            session=object(),
        )

    assert job.stage == "rolling_back"
    fail_parent.assert_not_awaited()


@pytest.mark.asyncio
async def test_dense_failure_after_bm25_completion_uses_parent_rollback(
    monkeypatch,
    recording_async_session_factory,
):
    job = _job(status="running", build_bm25=True, requested_bm25_index_name="policy lexical")
    snapshot = _chunk_set_snapshot()
    dense = SimpleNamespace(id=88, status="building")
    child = SimpleNamespace(id=71, status="completed", result_bm25_index_id=202)
    rollback_calls = []

    async def get_job(*_args):
        return job

    async def create_chunk_set(current_job, _session):
        current_job.corpus_chunk_set_id = snapshot.chunk_set.id
        return snapshot

    async def create_candidate(current_job, current_snapshot, _session):
        assert current_job is job
        assert current_snapshot is snapshot
        return dense

    async def process(current_job, _session):
        assert current_job is job
        return SimpleNamespace(successful_documents=1, chunks_created=2)

    async def rollback(*args, **kwargs):
        rollback_calls.append((args, kwargs))
        job.status = "failed"
        return job

    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "get_full_corpus_index_pipe_job_by_id", get_job)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_process_documents", process)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_create_job_chunk_set", create_chunk_set)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_create_candidate_index", create_candidate)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_queue_bm25_child", AsyncMock(return_value=child))
    monkeypatch.setattr(full_corpus_index_pipe_job, "_wait_for_bm25_child", AsyncMock(return_value=child))
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_bm25_indices_repo, "link_corpus_bm25_index_to_full_pipe_job", AsyncMock())
    monkeypatch.setattr(full_corpus_index_pipe_job, "_embed_candidate", AsyncMock(side_effect=RuntimeError("dense exploded")))
    monkeypatch.setattr(full_corpus_index_pipe_job, "_rollback_parent_artifacts", rollback, raising=False)
    monkeypatch.setattr(full_corpus_index_pipe_job, "AsyncSessionLocal", recording_async_session_factory)

    result = await full_corpus_index_pipe_job.run_full_corpus_index_pipe_job_srvc(9)

    assert result.status == "failed"
    assert len(rollback_calls) == 1
    assert rollback_calls[0][1]["terminal_status"] == "failed"
    assert "dense exploded" in rollback_calls[0][1]["detail"]


@pytest.mark.asyncio
async def test_queue_job_allows_same_configuration_with_different_name(monkeypatch):
    async def fake_get_corpus_by_id(corpus_id, session):
        return SimpleNamespace(id=corpus_id)

    async def fake_get_profile(profile_id, session):
        return SimpleNamespace(id=profile_id, strategy="recursive", config={"chunk_size": 100, "chunk_overlap": 10})

    async def fake_get_store(store_id, session):
        return SimpleNamespace(id=store_id, embedding_dimensions=384)

    async def fake_get_corpus_raw_document_ids(corpus_id, session):
        return [7]

    async def fake_get_corpus_index_by_name(name, session):
        return None

    async def fake_get_corpus_index_by_vector_namespace(**kwargs):
        return None

    async def fake_get_chunk_set_by_name(*_args):
        return None

    async def fake_has_chunk_set_reservation(*_args):
        return False

    async def fake_get_replaceable_built_index(**kwargs):
        raise AssertionError("same-configuration indices should not be treated as replacements")

    async def fake_has_non_terminal(index_id, session):
        raise AssertionError("simulation guards should not run for parallel index creation")

    async def fake_has_knowledge_graphs(index_id, session):
        raise AssertionError("knowledge graph guards should not run for parallel index creation")

    async def fake_create_full_corpus_index_pipe_job(job_in, session):
        return _job(
            corpus_id=job_in.corpus_id,
            chunking_profile_id=job_in.chunking_profile_id,
            vector_store_id=job_in.vector_store_id,
            embedding_model=job_in.embedding_model,
            requested_index_name=job_in.requested_index_name,
            requested_chunk_set_name=job_in.requested_chunk_set_name,
            requested_vector_namespace=job_in.requested_vector_namespace,
        )

    async def fake_update_progress(job, session, **kwargs):
        for key, value in kwargs.items():
            setattr(job, key, value)
        return job

    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)
    monkeypatch.setattr(full_corpus_index_pipe_job.chunking_profiles_repo, "get_chunking_profile_by_id", fake_get_profile)
    monkeypatch.setattr(full_corpus_index_pipe_job.vector_stores_repo, "get_vector_store_by_id", fake_get_store)
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_repo, "get_corpus_raw_document_ids", fake_get_corpus_raw_document_ids)
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_indices_repo, "get_corpus_index_by_name", fake_get_corpus_index_by_name)
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_indices_repo, "get_corpus_index_by_vector_namespace", fake_get_corpus_index_by_vector_namespace)
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_chunk_sets_repo, "get_corpus_chunk_set_by_name", fake_get_chunk_set_by_name)
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "has_active_full_pipe_chunk_set_name_reservation", fake_has_chunk_set_reservation)
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_indices_repo, "get_replaceable_built_index", fake_get_replaceable_built_index)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_has_non_terminal_simulations_for_index", fake_has_non_terminal)
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_indices_repo, "has_knowledge_graphs", fake_has_knowledge_graphs)
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "create_full_corpus_index_pipe_job", fake_create_full_corpus_index_pipe_job)
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "update_full_corpus_index_pipe_job_progress", fake_update_progress)

    queued = await full_corpus_index_pipe_job.queue_full_corpus_index_pipe_job_srvc(
        FullCorpusIndexPipeJobCreate(
            corpus_id=1,
            chunking_profile_id=2,
            vector_store_id=3,
            embedding_model="mini-l6-v2",
            requested_index_name="policy-index-v2",
            requested_chunk_set_name="  August policy set  ",
            build_bm25=False,
        ),
        SimpleNamespace(id=5),
        object(),
    )

    assert queued.id == 9
    assert queued.requested_index_name == "policy-index-v2"
    assert queued.requested_chunk_set_name == "August policy set"
    assert queued.total_documents == 1


@pytest.mark.asyncio
async def test_queue_job_rejects_duplicate_index_name(monkeypatch):
    async def fake_get_corpus_by_id(corpus_id, session):
        return SimpleNamespace(id=corpus_id)

    async def fake_get_profile(profile_id, session):
        return SimpleNamespace(id=profile_id, strategy="recursive", config={"chunk_size": 100, "chunk_overlap": 10})

    async def fake_get_store(store_id, session):
        return SimpleNamespace(id=store_id, embedding_dimensions=384)

    async def fake_get_corpus_raw_document_ids(corpus_id, session):
        return [7]

    async def fake_get_corpus_index_by_name(name, session):
        return SimpleNamespace(id=77)

    async def fake_create_full_corpus_index_pipe_job(job_in, session):
        raise AssertionError("duplicate index names should fail before job creation")

    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)
    monkeypatch.setattr(full_corpus_index_pipe_job.chunking_profiles_repo, "get_chunking_profile_by_id", fake_get_profile)
    monkeypatch.setattr(full_corpus_index_pipe_job.vector_stores_repo, "get_vector_store_by_id", fake_get_store)
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_repo, "get_corpus_raw_document_ids", fake_get_corpus_raw_document_ids)
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_indices_repo, "get_corpus_index_by_name", fake_get_corpus_index_by_name)
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "create_full_corpus_index_pipe_job", fake_create_full_corpus_index_pipe_job)

    with pytest.raises(ValueError, match="Corpus index name already exists"):
        await full_corpus_index_pipe_job.queue_full_corpus_index_pipe_job_srvc(
            FullCorpusIndexPipeJobCreate(
                corpus_id=1,
                chunking_profile_id=2,
                vector_store_id=3,
                embedding_model="mini-l6-v2",
                requested_index_name="policy-index",
                requested_chunk_set_name="August policy set",
                build_bm25=False,
            ),
            SimpleNamespace(id=5),
            object(),
        )


@pytest.mark.asyncio
async def test_queue_job_rejects_duplicate_vector_namespace(monkeypatch):
    async def fake_get_corpus_by_id(corpus_id, session):
        return SimpleNamespace(id=corpus_id)

    async def fake_get_profile(profile_id, session):
        return SimpleNamespace(id=profile_id, strategy="recursive", config={"chunk_size": 100, "chunk_overlap": 10})

    async def fake_get_store(store_id, session):
        return SimpleNamespace(id=store_id, embedding_dimensions=384)

    async def fake_get_corpus_raw_document_ids(corpus_id, session):
        return [7]

    async def fake_get_corpus_index_by_name(name, session):
        return None

    async def fake_get_corpus_index_by_vector_namespace(**kwargs):
        return SimpleNamespace(id=77, vector_store_id=kwargs["vector_store_id"])

    async def fake_create_full_corpus_index_pipe_job(job_in, session):
        raise AssertionError("duplicate vector namespaces should fail before job creation")

    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)
    monkeypatch.setattr(full_corpus_index_pipe_job.chunking_profiles_repo, "get_chunking_profile_by_id", fake_get_profile)
    monkeypatch.setattr(full_corpus_index_pipe_job.vector_stores_repo, "get_vector_store_by_id", fake_get_store)
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_repo, "get_corpus_raw_document_ids", fake_get_corpus_raw_document_ids)
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_indices_repo, "get_corpus_index_by_name", fake_get_corpus_index_by_name)
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_indices_repo, "get_corpus_index_by_vector_namespace", fake_get_corpus_index_by_vector_namespace)
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "create_full_corpus_index_pipe_job", fake_create_full_corpus_index_pipe_job)

    with pytest.raises(ValueError, match="Vector namespace already exists for this vector store"):
        await full_corpus_index_pipe_job.queue_full_corpus_index_pipe_job_srvc(
            FullCorpusIndexPipeJobCreate(
                corpus_id=1,
                chunking_profile_id=2,
                vector_store_id=3,
                embedding_model="mini-l6-v2",
                requested_index_name="policy-index-v2",
                requested_chunk_set_name="August policy set",
                requested_vector_namespace="shared-namespace",
                build_bm25=False,
            ),
            SimpleNamespace(id=5),
            object(),
        )


@pytest.mark.asyncio
async def test_activate_candidate_index_does_not_infer_replacement(monkeypatch):
    job = _job(requested_index_name="policy-index-v2")
    candidate_index = SimpleNamespace(id=88, status="built")

    async def fake_get_replaceable_built_index(**kwargs):
        raise AssertionError("activation should not look up same-configuration replacement targets")

    async def fake_activate_candidate_index(**kwargs):
        assert "replaced_index" not in kwargs
        kwargs["candidate_index"].name = kwargs["requested_name"]
        return kwargs["candidate_index"], None

    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_indices_repo, "get_replaceable_built_index", fake_get_replaceable_built_index)
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_indices_repo, "activate_candidate_index", fake_activate_candidate_index)

    result = await full_corpus_index_pipe_job._activate_candidate_index(job, candidate_index, object())

    assert result.candidate_corpus_index_id == 88
    assert result.replaced_corpus_index_id is None
    assert candidate_index.name == "policy-index-v2"


@pytest.mark.asyncio
async def test_queue_job_rejects_when_vector_store_dimensions_are_unset(monkeypatch):
    async def fake_get_corpus_by_id(corpus_id, session):
        return SimpleNamespace(id=corpus_id)

    async def fake_get_profile(profile_id, session):
        return SimpleNamespace(id=profile_id, strategy="recursive", config={"chunk_size": 100, "chunk_overlap": 10})

    async def fake_get_store(store_id, session):
        return SimpleNamespace(id=store_id, embedding_dimensions=None)

    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)
    monkeypatch.setattr(full_corpus_index_pipe_job.chunking_profiles_repo, "get_chunking_profile_by_id", fake_get_profile)
    monkeypatch.setattr(full_corpus_index_pipe_job.vector_stores_repo, "get_vector_store_by_id", fake_get_store)

    with pytest.raises(ValueError, match="Vector store dimensions are not set"):
        await full_corpus_index_pipe_job.queue_full_corpus_index_pipe_job_srvc(
            FullCorpusIndexPipeJobCreate(
                corpus_id=1,
                chunking_profile_id=2,
                vector_store_id=3,
                embedding_model="mini-l6-v2",
                requested_index_name="policy-index",
                requested_chunk_set_name="August policy set",
                build_bm25=False,
            ),
            SimpleNamespace(id=5),
            object(),
        )


@pytest.mark.asyncio
async def test_queue_job_rejects_when_vector_store_dimensions_mismatch(monkeypatch):
    async def fake_get_corpus_by_id(corpus_id, session):
        return SimpleNamespace(id=corpus_id)

    async def fake_get_profile(profile_id, session):
        return SimpleNamespace(id=profile_id, strategy="recursive", config={"chunk_size": 100, "chunk_overlap": 10})

    async def fake_get_store(store_id, session):
        return SimpleNamespace(id=store_id, embedding_dimensions=1536)

    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)
    monkeypatch.setattr(full_corpus_index_pipe_job.chunking_profiles_repo, "get_chunking_profile_by_id", fake_get_profile)
    monkeypatch.setattr(full_corpus_index_pipe_job.vector_stores_repo, "get_vector_store_by_id", fake_get_store)

    with pytest.raises(ValueError, match=r"Embedding model dimensions \(384\) do not match vector store dimensions \(1536\)"):
        await full_corpus_index_pipe_job.queue_full_corpus_index_pipe_job_srvc(
            FullCorpusIndexPipeJobCreate(
                corpus_id=1,
                chunking_profile_id=2,
                vector_store_id=3,
                embedding_model="mini-l6-v2",
                requested_index_name="policy-index",
                requested_chunk_set_name="August policy set",
                build_bm25=False,
            ),
            SimpleNamespace(id=5),
            object(),
        )


@pytest.mark.asyncio
async def test_run_job_completes_with_warnings_when_one_pdf_is_skipped(monkeypatch, recording_async_session_factory):
    captured_warnings = []
    job = _job(id=9)
    snapshot = _chunk_set_snapshot()
    candidate = SimpleNamespace(
        id=88,
        status="built",
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="a" * 64,
    )

    async def fake_get_job_by_id(job_id, session):
        assert job_id == 9
        return job

    async def fake_mark_running(job, session):
        job.status = "running"
        return job

    async def fake_create_chunk_set(current_job, session):
        current_job.corpus_chunk_set_id = snapshot.chunk_set.id
        return snapshot

    async def fake_create_candidate(current_job, current_snapshot, session):
        assert current_snapshot is snapshot
        return candidate

    async def fake_process_documents(job, session):
        captured_warnings.append(
            SimpleNamespace(
                id=1,
                raw_document_id=None,
                document_name="bad.pdf",
                stage="converting",
                message="Skipped bad.pdf",
                created_at=datetime.now(timezone.utc),
            )
        )
        return SimpleNamespace(successful_documents=1, chunks_created=12, chunks_indexed=12)

    async def fake_embed_candidate(job, candidate_index, current_snapshot, session):
        assert current_snapshot is snapshot
        return None

    async def fake_activate(job, candidate_index, session):
        return SimpleNamespace(candidate_corpus_index_id=88, replaced_corpus_index_id=None)

    async def fake_complete(job, session, **kwargs):
        job.status = kwargs["status"]
        job.candidate_corpus_index_id = kwargs["candidate_corpus_index_id"]
        return job

    async def fake_list_warnings(full_corpus_index_pipe_job_id, session):
        return captured_warnings

    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "get_full_corpus_index_pipe_job_by_id", fake_get_job_by_id)
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "mark_full_corpus_index_pipe_job_running", fake_mark_running)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_process_documents", fake_process_documents)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_create_job_chunk_set", fake_create_chunk_set)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_create_candidate_index", fake_create_candidate)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_embed_candidate", fake_embed_candidate)
    monkeypatch.setattr(
        full_corpus_index_pipe_job.corpus_indices_repo,
        "get_corpus_index_by_id",
        AsyncMock(return_value=candidate),
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job,
        "get_corpus_chunk_set_snapshot_srvc",
        AsyncMock(return_value=snapshot),
    )
    monkeypatch.setattr(full_corpus_index_pipe_job, "_activate_candidate_index", fake_activate)
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "mark_full_corpus_index_pipe_job_completed", fake_complete)
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "list_full_corpus_index_pipe_job_warnings", fake_list_warnings)

    monkeypatch.setattr(full_corpus_index_pipe_job, "AsyncSessionLocal", recording_async_session_factory)

    result = await full_corpus_index_pipe_job.run_full_corpus_index_pipe_job_srvc(job_id=9)

    assert result.status == "completed_with_warnings"
    assert result.candidate_corpus_index_id == 88
    assert len(result.warnings) == 1


@pytest.mark.asyncio
async def test_cancel_queued_full_corpus_index_pipe_job_requests_cancel_and_marks_job_cancelled(monkeypatch):
    job = _job(status="queued", stage="validating", candidate_corpus_index_id=88)
    candidate_index = SimpleNamespace(id=88, status="building")
    captured = []

    async def fake_get_job_by_id(job_id, session):
        return job

    async def fake_request_cancel(current_job, session):
        current_job.cancel_requested = True
        return current_job

    async def fake_get_candidate_index_by_id(index_id, session):
        return candidate_index

    async def fake_mark_cancelled(current_job, session, detail=None):
        current_job.status = "cancelled"
        current_job.stage = "finished"
        current_job.failure_detail = detail
        return current_job

    async def fake_mark_index_cancelled(index, reason, session):
        captured.append((index.id, reason))
        index.status = "cancelled"
        return index

    async def fake_read_job_detail(current_job, session):
        return current_job

    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "get_full_corpus_index_pipe_job_by_id", fake_get_job_by_id)
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "request_full_corpus_index_pipe_job_cancel", fake_request_cancel)
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_indices_repo, "get_corpus_index_by_id", fake_get_candidate_index_by_id)
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "mark_full_corpus_index_pipe_job_cancelled", fake_mark_cancelled)
    monkeypatch.setattr(full_corpus_index_pipe_job.corpus_indices_repo, "cancel_corpus_index_build", fake_mark_index_cancelled)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_read_job_detail", fake_read_job_detail)
    result = await full_corpus_index_pipe_job.cancel_full_corpus_index_pipe_job_srvc(9, object())

    assert result.status == "cancelled"
    assert result.cancel_requested is True
    assert captured == [(88, "Full corpus index pipe job cancelled by user")]


@pytest.mark.asyncio
async def test_run_job_marks_cancelled_when_task_is_cancelled(monkeypatch, recording_async_session_factory):
    job = _job(id=9, status="queued")

    async def fake_get_job_by_id(job_id, session):
        return job

    async def fake_mark_running(current_job, session):
        current_job.status = "running"
        return current_job

    async def fake_process_documents(current_job, session):
        raise asyncio.CancelledError()

    async def fake_rollback(
        current_job,
        candidate_index,
        *,
        terminal_status,
        detail,
        session,
    ):
        assert candidate_index is None
        assert terminal_status == "cancelled"
        current_job.status = "cancelled"
        current_job.stage = "finished"
        current_job.failure_detail = detail
        return current_job

    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "get_full_corpus_index_pipe_job_by_id", fake_get_job_by_id)
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "mark_full_corpus_index_pipe_job_running", fake_mark_running)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_process_documents", fake_process_documents)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_rollback_parent_artifacts", fake_rollback)
    monkeypatch.setattr(full_corpus_index_pipe_job, "AsyncSessionLocal", recording_async_session_factory)

    result = await full_corpus_index_pipe_job.run_full_corpus_index_pipe_job_srvc(job_id=9)

    assert result.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_running_job_returns_cancellation_requested_state(monkeypatch):
    job = _job(status="running", stage="cleaning", current_raw_document_id=12, current_document_name="policy.pdf")

    async def fake_get_job_by_id(job_id, session):
        return job

    async def fake_request_cancel(current_job, session):
        current_job.cancel_requested = True
        return current_job

    async def fake_read_job_detail(current_job, session):
        return current_job

    async def fake_mark_cancelled(*args, **kwargs):
        raise AssertionError("running jobs should not be marked cancelled immediately")

    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "get_full_corpus_index_pipe_job_by_id", fake_get_job_by_id)
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "request_full_corpus_index_pipe_job_cancel", fake_request_cancel)
    monkeypatch.setattr(full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo, "mark_full_corpus_index_pipe_job_cancelled", fake_mark_cancelled)
    monkeypatch.setattr(full_corpus_index_pipe_job, "_read_job_detail", fake_read_job_detail)
    result = await full_corpus_index_pipe_job.cancel_full_corpus_index_pipe_job_srvc(9, object())

    assert result.status == "running"
    assert result.cancel_requested is True
    assert result.stage == "cleaning"
    assert result.current_document_name == "policy.pdf"


@pytest.mark.asyncio
async def test_run_resumes_durable_rollback_without_rebuilding(monkeypatch, recording_async_session_factory):
    job = _job(
        status="running",
        stage="rolling_back",
        candidate_corpus_index_id=88,
        bm25_build_job_id=71,
        failure_detail="dense failed",
    )
    dense = SimpleNamespace(id=88, status="building")
    rollback = AsyncMock(return_value=SimpleNamespace(status="failed"))

    monkeypatch.setattr(
        full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo,
        "get_full_corpus_index_pipe_job_by_id",
        AsyncMock(return_value=job),
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job.corpus_indices_repo,
        "get_corpus_index_by_id",
        AsyncMock(return_value=dense),
    )
    monkeypatch.setattr(full_corpus_index_pipe_job, "_rollback_parent_artifacts", rollback)
    monkeypatch.setattr(
        full_corpus_index_pipe_job,
        "_create_candidate_index",
        AsyncMock(side_effect=AssertionError("rollback recovery must not rebuild")),
    )
    monkeypatch.setattr(full_corpus_index_pipe_job, "AsyncSessionLocal", recording_async_session_factory)

    result = await full_corpus_index_pipe_job.run_full_corpus_index_pipe_job_srvc(9)

    assert result.status == "failed"
    assert rollback.await_args.kwargs["terminal_status"] == "failed"
    assert rollback.await_args.kwargs["detail"] == "dense failed"
