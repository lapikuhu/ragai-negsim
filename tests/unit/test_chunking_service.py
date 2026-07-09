from types import SimpleNamespace

import pytest

from app.services import chunking_profile_runtime
from app.services import chunking_service


def _options(**overrides):
    values = {
        "preview": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _raw_document(raw_document_id=7, source_path="source.pdf", parsed_content="parsed text", source_status="available"):
    return SimpleNamespace(
        id=raw_document_id,
        name="parsed",
        source_path=source_path,
        source_hash="hash",
        source_size=10,
        source_mtime=None,
        source_status=source_status,
        parsed_content=parsed_content,
        uploaded_by_user_id=1,
    )


def _chunking_profile(profile_id=3):
    return SimpleNamespace(
        id=profile_id,
        name="default",
        strategy="recursive",
        config={"chunk_size": 1000, "chunk_overlap": 200, "separators": ["\n\n", "\n", " ", ""]},
    )


def test_resolve_chunking_profile_options_reads_recursive_profile():
    profile = SimpleNamespace(
        id=3,
        strategy="recursive",
        config={"chunk_size": 333, "chunk_overlap": 44, "separators": ["\n", " "]},
    )

    resolved = chunking_profile_runtime.resolve_chunking_profile_options(profile, preview=True)

    assert resolved.chunker == "recursive"
    assert resolved.chunk_size == 333
    assert resolved.chunk_overlap == 44
    assert resolved.separators == ["\n", " "]
    assert resolved.preview is True


def test_chunk_documents_dispatches_hybrid_with_combined_options(monkeypatch):
    from app.airag.chunking import chunkers

    documents = [SimpleNamespace(page_content="source", metadata={})]
    chunked_documents = [SimpleNamespace(page_content="chunk", metadata={})]
    captured = {}

    def fake_chunk_document_list_hybrid(input_documents, **kwargs):
        captured["documents"] = input_documents
        captured["kwargs"] = kwargs
        return chunked_documents

    monkeypatch.setattr(
        chunkers,
        "chunk_document_list_hybrid",
        fake_chunk_document_list_hybrid,
    )

    result = chunking_service._chunk_documents(
        documents,
        _options(
            chunker="hybrid",
            chunk_size=512,
            chunk_overlap=64,
            separators=["\n\n", "\n"],
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=85,
            buffer_size=2,
        ),
    )

    assert result == chunked_documents
    assert captured == {
        "documents": documents,
        "kwargs": {
            "breakpoint_threshold_type": "percentile",
            "breakpoint_threshold_amount": 85,
            "buffer_size": 2,
            "chunk_size": 512,
            "chunk_overlap": 64,
            "separators": ["\n\n", "\n"],
        },
    }


@pytest.mark.asyncio
async def test_chunk_raw_document_preview_does_not_persist(monkeypatch):
    chunked_documents = [
        SimpleNamespace(page_content="first chunk", metadata={"part": 1}),
        SimpleNamespace(page_content="second chunk", metadata={"part": 2}),
    ]

    async def fake_list_document_chunks(**kwargs):
        return []

    async def fail_bulk_create(chunks_in, session):
        raise AssertionError("preview mode should not persist chunks")

    monkeypatch.setattr(chunking_service, "list_document_chunks", fake_list_document_chunks)
    async def fake_verify_raw_document_source(raw_document, session):
        return raw_document

    monkeypatch.setattr(
        chunking_service,
        "verify_raw_document_source_srvc",
        fake_verify_raw_document_source,
    )
    monkeypatch.setattr(
        chunking_service,
        "_chunk_documents",
        lambda documents, options: chunked_documents,
    )
    monkeypatch.setattr(chunking_service, "bulk_create_document_chunks", fail_bulk_create)

    result = await chunking_service.chunk_raw_document_srvc(
        raw_document=_raw_document(),
        chunking_profile=_chunking_profile(),
        session=object(),
        options=_options(preview=True),
    )

    assert result.preview is True
    assert result.chunks_created == 2
    assert result.chunk_ids == []
    assert [chunk.content for chunk in result.chunks] == ["first chunk", "second chunk"]


@pytest.mark.asyncio
async def test_chunk_raw_document_requires_new_profile_when_chunks_exist(monkeypatch):
    async def fake_list_document_chunks(**kwargs):
        return [SimpleNamespace(id=1)]

    monkeypatch.setattr(chunking_service, "list_document_chunks", fake_list_document_chunks)
    async def fake_verify_raw_document_source(raw_document, session):
        return raw_document

    monkeypatch.setattr(
        chunking_service,
        "verify_raw_document_source_srvc",
        fake_verify_raw_document_source,
    )

    with pytest.raises(ValueError, match="already exist"):
        await chunking_service.chunk_raw_document_srvc(
            raw_document=_raw_document(),
            chunking_profile=_chunking_profile(),
            session=object(),
            options=_options(),
        )


@pytest.mark.asyncio
async def test_chunk_raw_document_persists_parsed_db_content(monkeypatch):
    chunked_documents = [SimpleNamespace(page_content="first chunk", metadata={"part": 1})]
    captured_chunks = []

    async def fake_list_document_chunks(**kwargs):
        return []

    async def fake_bulk_create(chunks_in, session):
        captured_chunks.extend(chunks_in)
        return [SimpleNamespace(id=101)]

    monkeypatch.setattr(chunking_service, "list_document_chunks", fake_list_document_chunks)
    async def fake_verify_raw_document_source(raw_document, session):
        return raw_document

    monkeypatch.setattr(
        chunking_service,
        "verify_raw_document_source_srvc",
        fake_verify_raw_document_source,
    )
    def fake_chunk_documents(documents, options):
        assert documents[0].page_content == "stored markdown"
        assert documents[0].metadata["source"] == "source.pdf"
        return chunked_documents

    monkeypatch.setattr(chunking_service, "_chunk_documents", fake_chunk_documents)
    monkeypatch.setattr(chunking_service, "bulk_create_document_chunks", fake_bulk_create)

    result = await chunking_service.chunk_raw_document_srvc(
        raw_document=_raw_document(parsed_content="stored markdown"),
        chunking_profile=_chunking_profile(),
        session=object(),
        options=_options(),
    )

    assert result.chunks_created == 1
    assert result.chunk_ids == [101]
    assert captured_chunks[0].content == "first chunk"
    assert captured_chunks[0].raw_document_id == 7
    assert captured_chunks[0].chunking_profile_id == 3


@pytest.mark.asyncio
async def test_chunk_corpus_chunks_linked_raw_documents(monkeypatch):
    raw_documents = {
        7: _raw_document(7, "first.pdf", "first parsed"),
        8: _raw_document(8, "second.pdf", "second parsed"),
    }

    async def fake_get_raw_document_ids(corpus_id, session):
        assert corpus_id == 11
        return [7, 8]

    async def fake_get_raw_document_by_id(raw_document_id, session):
        return raw_documents[raw_document_id]

    async def fake_chunk_raw_document(raw_document, chunking_profile, session, options):
        return chunking_service.RawDocumentChunkResult(
            raw_document_id=raw_document.id,
            chunking_profile_id=chunking_profile.id,
            chunker=chunking_profile.strategy,
            chunks_created=raw_document.id,
            chunk_ids=[raw_document.id * 10],
        )

    monkeypatch.setattr(
        chunking_service.corpus_repo,
        "get_corpus_raw_document_ids",
        fake_get_raw_document_ids,
    )
    monkeypatch.setattr(
        chunking_service.raw_documents_repo,
        "get_raw_document_by_id",
        fake_get_raw_document_by_id,
    )
    monkeypatch.setattr(chunking_service, "chunk_raw_document_srvc", fake_chunk_raw_document)

    result = await chunking_service.chunk_corpus_srvc(
        corpus=SimpleNamespace(id=11, name="corpus", created_by_user_id=1),
        chunking_profile=_chunking_profile(),
        session=object(),
        options=_options(),
    )

    assert result.corpus_id == 11
    assert result.chunks_created == 15
    assert [item.raw_document_id for item in result.raw_documents] == [7, 8]


@pytest.mark.asyncio
async def test_chunk_raw_document_blocks_when_source_is_not_available(monkeypatch):
    async def fake_verify_raw_document_source(raw_document, session):
        return raw_document

    monkeypatch.setattr(
        chunking_service,
        "verify_raw_document_source_srvc",
        fake_verify_raw_document_source,
    )

    with pytest.raises(ValueError, match="source is missing"):
        await chunking_service.chunk_raw_document_srvc(
            raw_document=_raw_document(source_status="missing"),
            chunking_profile=_chunking_profile(),
            session=object(),
            options=_options(),
        )
