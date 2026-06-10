from types import SimpleNamespace

import pytest

from app.services import ingestion_service


@pytest.mark.asyncio
async def test_ingest_raw_document_persists_parsed_chunks(monkeypatch):
    raw_document = SimpleNamespace(
        id=7,
        name="sample",
        source_path="sample.pdf",
        source_hash="hash",
        source_size=10,
        source_mtime=None,
        source_status="available",
        parsed_content=None,
        uploaded_by_user_id=1,
    )
    chunking_profile = SimpleNamespace(
        id=3,
        name="default",
        strategy="recursive",
        config={"chunk_size": 444, "chunk_overlap": 55, "separators": ["\n\n", "\n"]},
    )
    options = SimpleNamespace(
        header_depth=2,
        dynamic_header_depth=False,
    )
    parsed_chunks = [
        SimpleNamespace(page_content="first chunk", metadata={"section": "intro"}),
        SimpleNamespace(page_content="second chunk", metadata={"section": "terms"}),
    ]
    captured_chunks = []
    captured_parsed_content = []

    def fake_parse(path, received_options):
        assert path == "sample.pdf"
        assert received_options.chunker == "recursive"
        assert received_options.chunk_size == 444
        assert received_options.chunk_overlap == 55
        return "stored markdown", parsed_chunks

    async def fake_update_parsed_content(raw_document, parsed_content, session):
        captured_parsed_content.append(parsed_content)
        raw_document.parsed_content = parsed_content
        return raw_document

    async def fake_bulk_create(chunks_in, session):
        captured_chunks.extend(chunks_in)
        return [
            SimpleNamespace(id=101),
            SimpleNamespace(id=102),
        ]

    monkeypatch.setattr(ingestion_service, "_parse_raw_document", fake_parse)
    async def fake_verify_raw_document_source(raw_document, session):
        return raw_document

    monkeypatch.setattr(
        ingestion_service,
        "verify_raw_document_source_srvc",
        fake_verify_raw_document_source,
    )
    monkeypatch.setattr(
        ingestion_service.raw_documents_repo,
        "update_raw_document_parsed_content",
        fake_update_parsed_content,
    )
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
    assert captured_parsed_content == ["stored markdown"]
    assert [chunk.content for chunk in captured_chunks] == ["first chunk", "second chunk"]
    assert [chunk.chunk_index for chunk in captured_chunks] == [0, 1]
    assert captured_chunks[0].raw_document_id == 7
    assert captured_chunks[0].chunking_profile_id == 3
    assert captured_chunks[0].chunk_metadata["section"] == "intro"
    assert captured_chunks[0].chunk_metadata["source"] == "sample.pdf"
    assert captured_chunks[0].indexing_job_id is None


@pytest.mark.asyncio
async def test_ingest_raw_document_sets_indexing_job_id_on_created_chunks(monkeypatch):
    raw_document = SimpleNamespace(
        id=7,
        name="sample",
        source_path="sample.pdf",
        source_hash="hash",
        source_size=10,
        source_mtime=None,
        source_status="available",
        parsed_content=None,
        uploaded_by_user_id=1,
    )
    chunking_profile = SimpleNamespace(
        id=3,
        name="default",
        strategy="recursive",
        config={"chunk_size": 444, "chunk_overlap": 55, "separators": ["\n\n", "\n"]},
    )
    captured_chunks = []

    monkeypatch.setattr(
        ingestion_service,
        "_parse_raw_document",
        lambda path, options: ("stored markdown", [SimpleNamespace(page_content="chunk", metadata={})]),
    )

    async def fake_verify_raw_document_source(raw_document, session):
        return raw_document

    async def fake_update_parsed_content(raw_document, parsed_content, session):
        return raw_document

    async def fake_bulk_create(chunks_in, session):
        captured_chunks.extend(chunks_in)
        return [SimpleNamespace(id=101)]

    monkeypatch.setattr(ingestion_service, "verify_raw_document_source_srvc", fake_verify_raw_document_source)
    monkeypatch.setattr(ingestion_service.raw_documents_repo, "update_raw_document_parsed_content", fake_update_parsed_content)
    monkeypatch.setattr(ingestion_service, "bulk_create_document_chunks", fake_bulk_create)

    await ingestion_service.ingest_raw_document_srvc(
        raw_document=raw_document,
        chunking_profile=chunking_profile,
        session=object(),
        options=SimpleNamespace(header_depth=2, dynamic_header_depth=False),
        indexing_job_id=44,
    )

    assert captured_chunks[0].indexing_job_id == 44


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
        config={"chunk_size": 444, "chunk_overlap": 55, "separators": ["\n\n", "\n"]},
    )
    options = SimpleNamespace(
        header_depth=2,
        dynamic_header_depth=False,
    )
    raw_documents = {
        7: SimpleNamespace(
            id=7,
            name="first",
            source_path="first.pdf",
            source_hash="hash-1",
            source_size=10,
            source_mtime=None,
            source_status="available",
            parsed_content=None,
            uploaded_by_user_id=1,
        ),
        8: SimpleNamespace(
            id=8,
            name="second",
            source_path="second.pdf",
            source_hash="hash-2",
            source_size=10,
            source_mtime=None,
            source_status="available",
            parsed_content=None,
            uploaded_by_user_id=1,
        ),
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


@pytest.mark.asyncio
async def test_ingest_raw_document_blocks_when_source_is_not_available(monkeypatch):
    raw_document = SimpleNamespace(
        id=7,
        name="sample",
        source_path="sample.pdf",
        source_hash="hash",
        source_size=10,
        source_mtime=None,
        source_status="changed",
        parsed_content=None,
        uploaded_by_user_id=1,
    )
    chunking_profile = SimpleNamespace(
        id=3,
        strategy="recursive",
        config={"chunk_size": 444, "chunk_overlap": 55, "separators": ["\n\n", "\n"]},
    )
    options = SimpleNamespace(
        header_depth=2,
        dynamic_header_depth=False,
    )

    async def fake_verify_raw_document_source(raw_document, session):
        return raw_document

    monkeypatch.setattr(
        ingestion_service,
        "verify_raw_document_source_srvc",
        fake_verify_raw_document_source,
    )

    with pytest.raises(ValueError, match="source is changed"):
        await ingestion_service.ingest_raw_document_srvc(
            raw_document=raw_document,
            chunking_profile=chunking_profile,
            session=object(),
            options=options,
        )


@pytest.mark.asyncio
async def test_ingest_raw_document_rejects_semantic_profile():
    chunking_profile = SimpleNamespace(
        id=3,
        strategy="semantic",
        config={"breakpoint_threshold_type": "percentile", "breakpoint_threshold_amount": 90, "buffer_size": 1},
    )

    async def fake_verify_raw_document_source(raw_document, session):
        return raw_document

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        ingestion_service,
        "verify_raw_document_source_srvc",
        fake_verify_raw_document_source,
    )

    with pytest.raises(ValueError, match="requires an embedding model"):
        await ingestion_service.ingest_raw_document_srvc(
            raw_document=SimpleNamespace(id=9, source_status="available", source_path="doc.pdf"),
            chunking_profile=chunking_profile,
            session=object(),
            options=SimpleNamespace(header_depth=2, dynamic_header_depth=False),
        )

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_ingest_raw_document_passes_embeddings_to_semantic_chunking(monkeypatch):
    raw_document = SimpleNamespace(
        id=7,
        name="sample",
        source_path="sample.pdf",
        source_hash="hash",
        source_size=10,
        source_mtime=None,
        source_status="available",
        parsed_content=None,
        uploaded_by_user_id=1,
    )
    chunking_profile = SimpleNamespace(
        id=3,
        name="semantic",
        strategy="semantic",
        config={
            "breakpoint_threshold_type": "percentile",
            "breakpoint_threshold_amount": 88,
            "buffer_size": 2,
        },
    )
    embeddings = object()
    captured_chunks = []

    def fake_parse(path, received_options, embeddings=None):
        assert path == "sample.pdf"
        assert received_options.chunker == "semantic"
        assert received_options.breakpoint_threshold_amount == 88
        assert received_options.buffer_size == 2
        assert embeddings is not None
        return "stored markdown", [SimpleNamespace(page_content="semantic chunk", metadata={"section": "intro"})]

    async def fake_verify_raw_document_source(raw_document, session):
        return raw_document

    async def fake_update_parsed_content(raw_document, parsed_content, session):
        return raw_document

    async def fake_bulk_create(chunks_in, session):
        captured_chunks.extend(chunks_in)
        return [SimpleNamespace(id=101)]

    monkeypatch.setattr(ingestion_service, "_parse_raw_document", fake_parse)
    monkeypatch.setattr(ingestion_service, "verify_raw_document_source_srvc", fake_verify_raw_document_source)
    monkeypatch.setattr(ingestion_service.raw_documents_repo, "update_raw_document_parsed_content", fake_update_parsed_content)
    monkeypatch.setattr(ingestion_service, "bulk_create_document_chunks", fake_bulk_create)

    result = await ingestion_service.ingest_raw_document_srvc(
        raw_document=raw_document,
        chunking_profile=chunking_profile,
        session=object(),
        options=SimpleNamespace(header_depth=2, dynamic_header_depth=False),
        embeddings=embeddings,
    )

    assert result.chunks_created == 1
    assert captured_chunks[0].content == "semantic chunk"
