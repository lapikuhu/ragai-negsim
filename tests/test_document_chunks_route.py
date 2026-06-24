from types import SimpleNamespace

import pytest

from app.web.routes import document_chunks_route


@pytest.mark.asyncio
async def test_list_document_chunks_route_delegates_filters(monkeypatch):
    captured = {}
    expected = SimpleNamespace(items=[SimpleNamespace(id=1)], skip=10, limit=5, total=11, has_more=True)

    async def fake_list_document_chunks_srvc(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(
        document_chunks_route.document_chunks_service,
        "list_document_chunks_srvc",
        fake_list_document_chunks_srvc,
    )

    session = object()

    result = await document_chunks_route.list_document_chunks(
        session=session,
        _admin=SimpleNamespace(id=1),
        page={"skip": 10, "limit": 5},
        raw_document_id=11,
        chunking_profile_id=3,
        has_indexed_chunks=False,
    )

    assert result == expected
    assert captured == {
        "session": session,
        "skip": 10,
        "limit": 5,
        "raw_document_id": 11,
        "chunking_profile_id": 3,
        "has_indexed_chunks": False,
    }
