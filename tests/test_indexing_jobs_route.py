from datetime import datetime, timezone

from app.schemas.indexing_jobs_schemas import IndexingJobDetail, IndexingJobQueued
from app.web.routes import indexing_jobs_route


def _queued_job(**overrides):
    values = {
        "id": 77,
        "corpus_id": 1,
        "chunking_profile_id": 2,
        "vector_store_id": 3,
        "embedding_model": "mini-l6-v2",
        "requested_index_name": "policy-index",
        "requested_vector_namespace": None,
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
        "failure_detail": None,
    }
    values.update(overrides)
    return IndexingJobQueued(**values)


def _job_detail(**overrides):
    values = _queued_job(**overrides).model_dump()
    values.setdefault("warnings", [])
    return IndexingJobDetail(**values)


def test_post_indexing_jobs_returns_202_and_starts_managed_task(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    captured = {}
    started_jobs = []

    async def fake_queue(job_in, session):
        captured["job_in"] = job_in
        captured["session"] = session
        return _queued_job(
            corpus_id=job_in.corpus_id,
            chunking_profile_id=job_in.chunking_profile_id,
            vector_store_id=job_in.vector_store_id,
            embedding_model=job_in.embedding_model,
            requested_index_name=job_in.requested_index_name,
        )

    def fake_start(job_id):
        started_jobs.append(job_id)
        return f"task-{job_id}"

    monkeypatch.setattr(indexing_jobs_route.indexing_jobs_service, "queue_indexing_job_srvc", fake_queue)
    monkeypatch.setattr(indexing_jobs_route.indexing_jobs_service, "start_indexing_job_task", fake_start)

    override_current_user(username="admin", roles=["admin"])
    session = override_session()
    allow_roles("admin")

    response = api_client.post(
        "/indexing-jobs/",
        json={
            "corpus_id": 1,
            "chunking_profile_id": 2,
            "vector_store_id": 3,
            "embedding_model": "mini-l6-v2",
            "requested_index_name": "policy-index",
        },
    )

    assert response.status_code == 202
    assert response.json() == _queued_job().model_dump(mode="json")
    assert captured["session"] is session
    assert captured["job_in"].requested_index_name == "policy-index"
    assert started_jobs == [77]


def test_get_active_indexing_job_returns_204_when_none_running(
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

    monkeypatch.setattr(indexing_jobs_route.indexing_jobs_service, "get_active_indexing_job_srvc", fake_get_active)

    override_current_user(username="admin", roles=["admin"])
    session = override_session()
    allow_roles("admin")

    response = api_client.get("/indexing-jobs/active")

    assert response.status_code == 204
    assert response.content == b""
    assert captured["session"] is session


def test_cancel_indexing_job_returns_updated_job(
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

    monkeypatch.setattr(indexing_jobs_route.indexing_jobs_service, "cancel_indexing_job_srvc", fake_cancel)

    override_current_user(username="admin", roles=["admin"])
    session = override_session()
    allow_roles("admin")

    response = api_client.post("/indexing-jobs/44/cancel")

    assert response.status_code == 200
    assert response.json() == _job_detail(id=44, status="cancelled", stage="finished").model_dump(mode="json")
    assert captured == {"job_id": 44, "session": session}
