from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from app.schemas.corpus_bm25_build_jobs_schemas import CorpusBm25BuildJobRead
from app.web.routes import corpus_bm25_build_jobs_route as route


def _read():
    return CorpusBm25BuildJobRead(
        id=9,
        requested_artifact_name="policy bm25",
        corpus_id=11,
        chunking_profile_id=3,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="c" * 64,
        requested_by_user_id=5,
        document_chunk_ids_checksum="c" * 64,
        distinct_document_count=1,
        chunk_count=2,
        status="queued",
        stage="queued",
        cancel_requested=False,
        queued_at=datetime(2026, 8, 13, tzinfo=timezone.utc),
    )


def test_queue_bm25_build_job_returns_202_and_wakes_coordinator(
    api_client, override_current_user, override_session, allow_roles, monkeypatch
):
    queue = AsyncMock(return_value=_read())
    wake = Mock()
    monkeypatch.setattr(route.service, "queue_corpus_bm25_build_job_srvc", queue)
    monkeypatch.setattr(route, "wake_corpus_bm25_build_coordinator", wake)
    override_current_user(username="admin", roles=["admin"])
    allow_roles("admin")
    override_session()

    response = api_client.post("/corpus-bm25-build-jobs/", json={
        "requested_artifact_name": "policy bm25",
        "corpus_chunk_set_id": 21,
    })

    assert response.status_code == 202
    assert response.json()["id"] == 9
    request = queue.await_args.args[0]
    assert request.requested_artifact_name == "policy bm25"
    assert request.corpus_chunk_set_id == 21
    wake.assert_called_once_with()
