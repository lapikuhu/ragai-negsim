from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services import document_chunks_service


def _chunk(chunk_id=5):
    return SimpleNamespace(
        id=chunk_id,
        raw_document_id=11,
        raw_document=SimpleNamespace(id=11, name="Negotiation PDF"),
        chunking_profile_id=3,
        chunking_profile=SimpleNamespace(id=3, name="Recursive 1k", strategy="recursive"),
        indexing_job_id=77,
        chunk_index=2,
        content="secret chunk body",
        chunk_metadata={"page": 4},
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        last_updated=datetime(2026, 6, 2, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_list_document_chunks_returns_enriched_rows_with_content(monkeypatch):
    async def fake_list_document_chunks(**kwargs):
        return [_chunk()]

    async def fake_get_corpus_index_ids(chunk_id, session):
        assert chunk_id == 5
        return [9, 10]

    async def fake_count_document_chunks(**kwargs):
        return 42

    monkeypatch.setattr(
        document_chunks_service.document_chunks_repo,
        "list_document_chunks",
        fake_list_document_chunks,
    )
    monkeypatch.setattr(
        document_chunks_service.document_chunks_repo,
        "get_document_chunk_corpus_index_ids",
        fake_get_corpus_index_ids,
    )
    monkeypatch.setattr(
        document_chunks_service.document_chunks_repo,
        "count_document_chunks",
        fake_count_document_chunks,
    )

    response = await document_chunks_service.list_document_chunks_srvc(
        session=object(),
        skip=20,
        limit=20,
        raw_document_id=11,
        chunking_profile_id=3,
        has_indexed_chunks=True,
    )

    assert response.skip == 20
    assert response.limit == 20
    assert response.total == 42
    assert response.has_more is True
    assert len(response.items) == 1
    row = response.items[0]
    assert row.id == 5
    assert row.raw_document_name == "Negotiation PDF"
    assert row.chunking_profile_name == "Recursive 1k"
    assert row.chunking_strategy == "recursive"
    assert row.corpus_index_ids == [9, 10]
    assert row.indexed_count == 2
    assert row.is_indexed is True
    assert row.content == "secret chunk body"
