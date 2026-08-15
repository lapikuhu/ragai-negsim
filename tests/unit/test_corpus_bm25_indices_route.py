from datetime import datetime, timezone

from app.schemas.corpus_bm25_indices_schemas import CorpusBm25IndexMetadata
from app.web.routes import corpus_bm25_indices_route


def _metadata() -> CorpusBm25IndexMetadata:
    now = datetime(2026, 8, 4, tzinfo=timezone.utc)
    return CorpusBm25IndexMetadata(
        id=17,
        name="Contracts BM25",
        corpus_id=11,
        chunking_profile_id=3,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="c" * 64,
        status="built",
        format_version="pickle-zlib-v1",
        document_count=24,
        document_chunk_ids_checksum="d" * 64,
        compressed_artifact_checksum="a" * 64,
        built_at=now,
        created_at=now,
        last_updated=now,
        build_error=None,
        created_by_full_corpus_index_pipe_job_id=None,
    )


def test_bm25_metadata_list_is_present_in_openapi(test_app):
    operation = test_app.openapi()["paths"]["/corpus-bm25-indices/"]["get"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "items": {"$ref": "#/components/schemas/CorpusBm25IndexMetadata"},
        "type": "array",
        "title": "Response List Corpus Bm25 Indices Corpus Bm25 Indices  Get",
    }


def test_list_bm25_indices_returns_safe_paginated_filtered_metadata(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    captured = {}

    async def fake_list(*, session, skip, limit, corpus_id, chunking_profile_id, status):
        captured.update(
            session=session,
            skip=skip,
            limit=limit,
            corpus_id=corpus_id,
            chunking_profile_id=chunking_profile_id,
            status=status,
        )
        return [_metadata()]

    monkeypatch.setattr(
        corpus_bm25_indices_route.corpus_bm25_indices_service,
        "list_corpus_bm25_indices_srvc",
        fake_list,
    )
    override_current_user(username="admin", roles=["admin"])
    session = override_session()
    allow_roles("admin")

    response = api_client.get(
        "/corpus-bm25-indices/?skip=5&limit=10&corpus_id=11&chunking_profile_id=3&status=built"
    )

    assert response.status_code == 200
    assert response.json() == [_metadata().model_dump(mode="json")]
    assert "artifact" not in response.json()[0]
    assert captured == {
        "session": session,
        "skip": 5,
        "limit": 10,
        "corpus_id": 11,
        "chunking_profile_id": 3,
        "status": "built",
    }


def test_list_bm25_indices_requires_admin(
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    override_current_user(username="student", roles=["student"])
    override_session()
    allow_roles("student")

    response = api_client.get("/corpus-bm25-indices/")

    assert response.status_code == 403


def test_list_bm25_indices_maps_invalid_status_to_conflict(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    async def fake_list(**_kwargs):
        raise ValueError("Unsupported corpus BM25 index status: unknown")

    monkeypatch.setattr(
        corpus_bm25_indices_route.corpus_bm25_indices_service,
        "list_corpus_bm25_indices_srvc",
        fake_list,
    )
    override_current_user(username="admin", roles=["admin"])
    override_session()
    allow_roles("admin")

    response = api_client.get("/corpus-bm25-indices/?status=unknown")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Unsupported corpus BM25 index status: unknown"
    }
