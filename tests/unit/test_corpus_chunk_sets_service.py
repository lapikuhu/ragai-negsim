from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.repositories.corpus_bm25_indices_repo import document_chunk_ids_checksum
from app.services import corpus_service


@pytest.mark.asyncio
async def test_chunk_set_summaries_group_by_profile_and_checksum(monkeypatch):
    chunks = [
        SimpleNamespace(id=12, raw_document_id=2, chunking_profile_id=3),
        SimpleNamespace(id=7, raw_document_id=1, chunking_profile_id=3),
        SimpleNamespace(id=20, raw_document_id=1, chunking_profile_id=4),
    ]
    monkeypatch.setattr(
        corpus_service.document_chunks_repo,
        "list_corpus_document_chunks",
        AsyncMock(return_value=chunks),
    )
    monkeypatch.setattr(
        corpus_service.chunking_profiles_repo,
        "get_chunking_profile_names_by_ids",
        AsyncMock(return_value={3: "recursive", 4: "semantic"}),
    )

    result = await corpus_service.list_corpus_chunk_set_summaries_srvc(11, object())

    assert [(item.chunking_profile_id, item.chunk_count) for item in result] == [(3, 2), (4, 1)]
    assert result[0].distinct_document_count == 2
    assert result[0].document_chunk_ids_checksum == document_chunk_ids_checksum([7, 12])


@pytest.mark.asyncio
async def test_chunk_set_summaries_return_empty_for_unchunked_corpus(monkeypatch):
    monkeypatch.setattr(
        corpus_service.document_chunks_repo,
        "list_corpus_document_chunks",
        AsyncMock(return_value=[]),
    )

    assert await corpus_service.list_corpus_chunk_set_summaries_srvc(11, object()) == []
