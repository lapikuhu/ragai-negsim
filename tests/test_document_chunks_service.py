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
async def test_list_document_chunks_returns_enriched_rows_without_content(monkeypatch):
    async def fake_list_document_chunks(**kwargs):
        return [_chunk()]

    async def fake_get_corpus_index_ids(chunk_id, session):
        assert chunk_id == 5
        return [9, 10]

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

    rows = await document_chunks_service.list_document_chunks_srvc(
        session=object(),
        skip=0,
        limit=20,
        raw_document_id=11,
        chunking_profile_id=3,
        has_indexed_chunks=True,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.id == 5
    assert row.raw_document_name == "Negotiation PDF"
    assert row.chunking_profile_name == "Recursive 1k"
    assert row.chunking_strategy == "recursive"
    assert row.corpus_index_ids == [9, 10]
    assert row.indexed_count == 2
    assert row.is_indexed is True
    assert "content" not in row.model_dump()

