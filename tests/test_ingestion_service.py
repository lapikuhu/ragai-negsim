from types import SimpleNamespace

import pytest

from services import ingestion_service


@pytest.mark.asyncio
async def test_ingest_raw_document_persists_parsed_chunks(monkeypatch):
    raw_document = SimpleNamespace(
        id=7,
        name="sample",
        path="sample.pdf",
        uploaded_by_user_id=1,
    )
    chunking_profile = SimpleNamespace(
        id=3,
        name="default",
        strategy="recursive",
        config={},
    )
    options = SimpleNamespace(
        header_depth=2,
        dynamic_header_depth=False,
        chunk_size=1000,
        chunk_overlap=200,
        chunker="recursive",
    )
    parsed_chunks = [
        SimpleNamespace(page_content="first chunk", metadata={"section": "intro"}),
        SimpleNamespace(page_content="second chunk", metadata={"section": "terms"}),
    ]
    captured_chunks = []

    def fake_parse(path, received_options):
        assert path == "sample.pdf"
        assert received_options is options
        return parsed_chunks

    async def fake_bulk_create(chunks_in, session):
        captured_chunks.extend(chunks_in)
        return [
            SimpleNamespace(id=101),
            SimpleNamespace(id=102),
        ]

    monkeypatch.setattr(ingestion_service, "_parse_raw_document", fake_parse)
    monkeypatch.setattr(ingestion_service, "bulk_create_document_chunks", fake_bulk_create)

    result = await ingestion_service.ingest_raw_document_srvc(
        raw_document=raw_document,
        chunking_profile=chunking_profile,
        session=object(),
        options=options,
    )

    assert result.raw_document_id == 7
    assert result.chunking_profile_id == 3
    assert result.chunks_created == 2
    assert result.chunk_ids == [101, 102]
    assert [chunk.content for chunk in captured_chunks] == ["first chunk", "second chunk"]
    assert [chunk.chunk_index for chunk in captured_chunks] == [0, 1]
    assert captured_chunks[0].raw_document_id == 7
    assert captured_chunks[0].chunking_profile_id == 3
    assert captured_chunks[0].chunk_metadata["section"] == "intro"
    assert captured_chunks[0].chunk_metadata["source"] == "sample.pdf"


@pytest.mark.asyncio
async def test_ingest_corpus_ingests_linked_raw_documents(monkeypatch):
    corpus = SimpleNamespace(
        id=11,
        name="corpus",
        created_by_user_id=1,
    )
    chunking_profile = SimpleNamespace(
        id=3,
        name="default",
        strategy="recursive",
        config={},
    )
    options = SimpleNamespace(
        header_depth=2,
        dynamic_header_depth=False,
        chunk_size=1000,
        chunk_overlap=200,
        chunker="recursive",
    )
    raw_documents = {
        7: SimpleNamespace(id=7, name="first", path="first.pdf", uploaded_by_user_id=1),
        8: SimpleNamespace(id=8, name="second", path="second.pdf", uploaded_by_user_id=1),
    }

    async def fake_get_raw_document_ids(corpus_id, session):
        assert corpus_id == 11
        return [7, 8]

    async def fake_get_raw_document_by_id(raw_document_id, session):
        return raw_documents[raw_document_id]

    async def fake_ingest_raw_document(raw_document, chunking_profile, session, options):
        return ingestion_service.RawDocumentIngestResult(
            raw_document_id=raw_document.id,
            chunking_profile_id=chunking_profile.id,
            chunks_created=raw_document.id,
            chunk_ids=[raw_document.id * 10],
        )

    monkeypatch.setattr(
        ingestion_service.corpus_repo,
        "get_corpus_raw_document_ids",
        fake_get_raw_document_ids,
    )
    monkeypatch.setattr(
        ingestion_service.raw_documents_repo,
        "get_raw_document_by_id",
        fake_get_raw_document_by_id,
    )
    monkeypatch.setattr(
        ingestion_service,
        "ingest_raw_document_srvc",
        fake_ingest_raw_document,
    )

    result = await ingestion_service.ingest_corpus_srvc(
        corpus=corpus,
        chunking_profile=chunking_profile,
        session=object(),
        options=options,
    )

    assert result.corpus_id == 11
    assert result.chunking_profile_id == 3
    assert result.chunks_created == 15
    assert [item.raw_document_id for item in result.raw_documents] == [7, 8]
