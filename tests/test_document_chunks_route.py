from datetime import datetime, timezone

from app.schemas.document_chunks_schemas import DocumentChunkAdminRead, DocumentChunkListResponse
from app.web.routes import document_chunks_route


def test_list_document_chunks_route_delegates_filters(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    captured = {}
    expected = DocumentChunkListResponse(
        items=[
            DocumentChunkAdminRead(
                id=1,
                raw_document_id=11,
                raw_document_name="Negotiation PDF",
                chunking_profile_id=3,
                chunking_profile_name="Recursive 1k",
                chunking_strategy="recursive",
                indexing_job_id=77,
                chunk_index=2,
                content="secret chunk body",
                chunk_metadata={"page": 4},
                corpus_index_ids=[9, 10],
                indexed_count=2,
                is_indexed=True,
                created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
                last_updated=datetime(2026, 6, 2, tzinfo=timezone.utc),
            )
        ],
        skip=10,
        limit=5,
        total=11,
        has_more=True,
    )

    async def fake_list_document_chunks_srvc(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(
        document_chunks_route.document_chunks_service,
        "list_document_chunks_srvc",
        fake_list_document_chunks_srvc,
    )

    override_current_user(username="admin", roles=["admin"])
    session = override_session()
    allow_roles("admin")

    response = api_client.get(
        "/document-chunks/?skip=10&limit=5&raw_document_id=11&chunking_profile_id=3&has_indexed_chunks=false"
    )

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")
    assert captured == {
        "session": session,
        "skip": 10,
        "limit": 5,
        "raw_document_id": 11,
        "chunking_profile_id": 3,
        "has_indexed_chunks": False,
    }
