from datetime import datetime, timezone

from app.schemas.full_corpus_index_pipe_jobs_schemas import FullCorpusIndexPipeJobDetail, FullCorpusIndexPipeJobQueued
from app.web.routes import full_corpus_index_pipe_jobs_route


def _queued_job(**overrides):
    values = {
        "id": 77,
        "corpus_id": 1,
        "chunking_profile_id": 2,
        "vector_store_id": 3,
        "embedding_model": "mini-l6-v2",
        "requested_index_name": "policy-index",
        "requested_chunk_set_name": "August policy set",
        "requested_vector_namespace": None,
        "build_bm25": True,
        "requested_bm25_index_name": "policy lexical",
        "status": "queued",
        "stage": "validating",
        "cancel_requested": False,
        "current_raw_document_id": None,
        "current_document_name": None,
        "total_documents": 1,
        "processed_documents": 0,
        "chunks_created": 0,
        "chunks_indexed": 0,
        "queued_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "started_at": None,
        "completed_at": None,
        "candidate_corpus_index_id": None,
        "replaced_corpus_index_id": None,
        "requested_by_user_id": 5,
        "bm25_build_job_id": None,
        "corpus_chunk_set_id": None,
        "failure_detail": None,
    }
    values.update(overrides)
    return FullCorpusIndexPipeJobQueued(**values)


def _job_detail(**overrides):
    values = _queued_job(**overrides).model_dump()
    values.setdefault("warnings", [])
    return FullCorpusIndexPipeJobDetail(**values)


def test_post_full_corpus_index_pipe_jobs_returns_202_and_wakes_coordinator(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    captured = {}
    wake_calls = []

    async def fake_queue(job_in, current_user, session):
        captured["job_in"] = job_in
        captured["current_user"] = current_user
        captured["session"] = session
        return _queued_job(
            corpus_id=job_in.corpus_id,
            chunking_profile_id=job_in.chunking_profile_id,
            vector_store_id=job_in.vector_store_id,
            embedding_model=job_in.embedding_model,
            requested_index_name=job_in.requested_index_name,
            requested_chunk_set_name=job_in.requested_chunk_set_name,
            build_bm25=job_in.build_bm25,
            requested_bm25_index_name=job_in.requested_bm25_index_name,
        )

    monkeypatch.setattr(full_corpus_index_pipe_jobs_route.full_corpus_index_pipe_job, "queue_full_corpus_index_pipe_job_srvc", fake_queue)
    monkeypatch.setattr(
        full_corpus_index_pipe_jobs_route,
        "wake_full_corpus_index_pipe_coordinator",
        lambda: wake_calls.append("wake"),
        raising=False,
    )

    admin = override_current_user(username="admin", roles=["admin"])
    session = override_session()
    allow_roles("admin")

    response = api_client.post(
        "/full-corpus-index-pipe-jobs/",
        json={
            "corpus_id": 1,
            "chunking_profile_id": 2,
            "vector_store_id": 3,
            "embedding_model": "mini-l6-v2",
            "requested_index_name": "policy-index",
            "requested_chunk_set_name": "August policy set",
            "requested_bm25_index_name": "policy lexical",
        },
    )

    assert response.status_code == 202
    assert response.json() == _queued_job().model_dump(mode="json")
    assert captured["session"] is session
    assert captured["current_user"] is admin
    assert captured["job_in"].requested_index_name == "policy-index"
    assert captured["job_in"].requested_chunk_set_name == "August policy set"
    assert captured["job_in"].build_bm25 is True
    assert captured["job_in"].requested_bm25_index_name == "policy lexical"
    assert wake_calls == ["wake"]


def test_get_active_full_corpus_index_pipe_job_returns_204_when_none_running(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    captured = {}

    async def fake_get_active(session):
        captured["session"] = session
        return None

    monkeypatch.setattr(full_corpus_index_pipe_jobs_route.full_corpus_index_pipe_job, "get_active_full_corpus_index_pipe_job_srvc", fake_get_active)

    override_current_user(username="admin", roles=["admin"])
    session = override_session()
    allow_roles("admin")

    response = api_client.get("/full-corpus-index-pipe-jobs/active")

    assert response.status_code == 204
    assert response.content == b""
    assert captured["session"] is session


def test_cancel_full_corpus_index_pipe_job_returns_updated_job(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    captured = {}

    async def fake_cancel(job_id, session):
        captured["job_id"] = job_id
        captured["session"] = session
        return _job_detail(id=job_id, status="cancelled", stage="finished")

    monkeypatch.setattr(full_corpus_index_pipe_jobs_route.full_corpus_index_pipe_job, "cancel_full_corpus_index_pipe_job_srvc", fake_cancel)

    override_current_user(username="admin", roles=["admin"])
    session = override_session()
    allow_roles("admin")

    response = api_client.post("/full-corpus-index-pipe-jobs/44/cancel")

    assert response.status_code == 200
    assert response.json() == _job_detail(id=44, status="cancelled", stage="finished").model_dump(mode="json")
    assert captured == {"job_id": 44, "session": session}
