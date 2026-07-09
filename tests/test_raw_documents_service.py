from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.schemas.raw_documents_schemas import RawDocumentCreate, RawDocumentUpdate
from app.services import raw_documents_service
from app.web.routes import raw_documents_route


def _now() -> datetime:
    return datetime.now(timezone.utc)


class _FakeUpload:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content
        self._position = 0

    async def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = len(self._content) - self._position
        start = self._position
        end = min(start + size, len(self._content))
        self._position = end
        return self._content[start:end]

    async def seek(self, position: int) -> None:
        self._position = position


def test_raw_document_metadata_accepts_integer_year_and_normalizes_blanks():
    raw_document = RawDocumentCreate(
        name="brief",
        description=None,
        source_path="brief.pdf",
        document_title="  Negotiation Brief  ",
        document_author="  Ada Lovelace  ",
        document_year=2026,
    )

    assert raw_document.document_title == "Negotiation Brief"
    assert raw_document.document_author == "Ada Lovelace"
    assert raw_document.document_year == 2026

    update = RawDocumentUpdate(
        document_title=" ",
        document_author="",
        document_year=None,
    )

    assert update.document_title is None
    assert update.document_author is None
    assert update.document_year is None


@pytest.mark.parametrize("document_year", [0, -44, 2026])
def test_raw_document_metadata_accepts_any_integer_year(document_year):
    raw_document = RawDocumentCreate(
        name="brief",
        description=None,
        source_path="brief.pdf",
        document_year=document_year,
    )

    assert raw_document.document_year == document_year


@pytest.mark.parametrize("document_year", ["2026", "2026-07-05", "2026.0", "abc"])
def test_raw_document_metadata_rejects_non_integer_document_year(document_year):
    with pytest.raises(ValueError):
        RawDocumentCreate(
            name="brief",
            description=None,
            source_path="brief.pdf",
            document_year=document_year,
        )


@pytest.mark.asyncio
async def test_create_uploaded_raw_document_rejects_duplicate_filename(
    tmp_path,
    monkeypatch,
    fake_user_factory,
    recording_async_session_factory,
):
    session = recording_async_session_factory()
    source_dir = tmp_path / "raw_docs_store"
    source_dir.mkdir()
    existing_file = source_dir / "brief.pdf"
    existing_file.write_bytes(b"%PDF-1.4\n%%EOF")

    monkeypatch.setattr(raw_documents_service.settings, "RAW_DOCS_DIR", str(source_dir))

    upload = _FakeUpload("brief.pdf", b"%PDF-1.4\n%%EOF")

    with pytest.raises(ValueError, match="already exists"):
        await raw_documents_service.create_uploaded_raw_document_srvc(
            name="brief",
            description=None,
            document_title=None,
            document_author=None,
            document_year=None,
            corpus_ids=[],
            upload=upload,
            session=session,
            current_user=fake_user_factory(user_id=1),
        )


@pytest.mark.asyncio
async def test_create_uploaded_raw_document_rejects_upload_larger_than_configured_limit(
    tmp_path,
    monkeypatch,
    fake_user_factory,
    recording_async_session_factory,
):
    session = recording_async_session_factory()
    source_dir = tmp_path / "raw_docs_store"
    source_dir.mkdir()
    monkeypatch.setattr(raw_documents_service.settings, "RAW_DOCS_DIR", str(source_dir))
    monkeypatch.setattr(raw_documents_service.settings, "MAX_UPLOAD_SIZE", 12)

    upload = _FakeUpload("brief.pdf", b"%PDF-1.4\n%%EOF")

    with pytest.raises(ValueError, match="exceeds the maximum allowed size"):
        await raw_documents_service.create_uploaded_raw_document_srvc(
            name="brief",
            description=None,
            document_title=None,
            document_author=None,
            document_year=None,
            corpus_ids=[],
            upload=upload,
            session=session,
            current_user=fake_user_factory(user_id=1),
        )

    assert not (source_dir / "brief.pdf").exists()


@pytest.mark.asyncio
async def test_create_raw_document_route_forwards_bibliographic_metadata(
    monkeypatch,
    fake_user_factory,
    recording_async_session_factory,
):
    captured = {}
    session = recording_async_session_factory()
    created = SimpleNamespace(
        id=21,
        name="alpha brief",
        description="Uploaded for testing",
        document_title="Negotiation Brief",
        document_author="Ada Lovelace",
        document_year=2026,
        source_path="raw/alpha.pdf",
        source_hash="abc123",
        source_size=2048,
        source_mtime=_now(),
        source_status="available",
        uploaded_at=_now(),
        uploaded_by_user_id=1,
        uploaded_by=SimpleNamespace(username="teacher"),
        parsed_at=None,
    )

    async def fake_create_uploaded_raw_document_srvc(**kwargs):
        captured.update(kwargs)
        return created

    monkeypatch.setattr(
        raw_documents_route,
        "create_uploaded_raw_document_srvc",
        fake_create_uploaded_raw_document_srvc,
    )

    result = await raw_documents_route.create_raw_document(
        name="alpha brief",
        description="Uploaded for testing",
        document_title="Negotiation Brief",
        document_author="Ada Lovelace",
        document_year=2026,
        corpus_ids=[],
        file=SimpleNamespace(filename="alpha.pdf"),
        session=session,
        current_user=fake_user_factory(user_id=1, username="teacher", roles="teacher"),
    )

    assert captured["session"] is session
    assert captured["document_title"] == "Negotiation Brief"
    assert captured["document_author"] == "Ada Lovelace"
    assert captured["document_year"] == 2026
    assert result.document_title == "Negotiation Brief"
    assert result.document_author == "Ada Lovelace"
    assert result.document_year == 2026


@pytest.mark.asyncio
async def test_update_raw_document_route_updates_bibliographic_metadata(
    monkeypatch,
    recording_async_session_factory,
):
    captured = {}
    session = recording_async_session_factory()
    raw_document = SimpleNamespace(id=21)
    updated = SimpleNamespace(
        id=21,
        name="alpha brief",
        description="Uploaded for testing",
        document_title="Updated title",
        document_author="Updated author",
        document_year=2027,
        source_path="raw/alpha.pdf",
        source_hash="abc123",
        source_size=2048,
        source_mtime=_now(),
        source_status="available",
        uploaded_at=_now(),
        uploaded_by_user_id=1,
        uploaded_by=SimpleNamespace(username="teacher"),
        associated_corpora=[],
    )

    async def fake_update_raw_document(raw_document_obj, update_data, session):
        captured["raw_document"] = raw_document_obj
        captured["update_data"] = update_data
        captured["session"] = session
        return updated

    monkeypatch.setattr(raw_documents_route.raw_documents_repo, "update_raw_document", fake_update_raw_document)

    result = await raw_documents_route.update_raw_document(
        raw_document=raw_document,
        update_data=RawDocumentUpdate(
            document_title="Updated title",
            document_author="Updated author",
            document_year=2027,
        ),
        session=session,
    )

    assert captured["raw_document"] is raw_document
    assert captured["update_data"].document_title == "Updated title"
    assert captured["update_data"].document_author == "Updated author"
    assert captured["update_data"].document_year == 2027
    assert captured["session"] is session
    assert result.document_title == "Updated title"
    assert result.document_author == "Updated author"
    assert result.document_year == 2027


@pytest.mark.asyncio
async def test_update_raw_document_route_maps_validation_error_to_conflict(
    monkeypatch,
    recording_async_session_factory,
):
    session = recording_async_session_factory()

    async def fake_update_raw_document(*_args, **_kwargs):
        raise ValueError("bad metadata")

    monkeypatch.setattr(raw_documents_route.raw_documents_repo, "update_raw_document", fake_update_raw_document)

    with pytest.raises(HTTPException) as exc_info:
        await raw_documents_route.update_raw_document(
            raw_document=SimpleNamespace(id=21),
            update_data=RawDocumentUpdate(document_year=2026),
            session=session,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "bad metadata"


@pytest.mark.asyncio
async def test_verify_raw_document_source_marks_missing(tmp_path, recording_async_session_factory):
    raw_document = SimpleNamespace(
        source_path=str(tmp_path / "missing.pdf"),
        source_hash="hash",
        source_size=10,
        source_mtime=_now(),
        source_status="available",
    )

    session = recording_async_session_factory()
    result = await raw_documents_service.verify_raw_document_source_srvc(raw_document, session)

    assert result.source_status == raw_documents_service.RAW_DOCUMENT_SOURCE_STATUS_MISSING
    assert session.commit_calls == 1


@pytest.mark.asyncio
async def test_verify_raw_document_source_marks_changed_when_hash_differs(tmp_path, recording_async_session_factory):
    source_file = tmp_path / "changed.pdf"
    source_file.write_bytes(b"new-bytes")
    raw_document = SimpleNamespace(
        source_path=str(source_file),
        source_hash="old-hash",
        source_size=9,
        source_mtime=_now(),
        source_status="available",
    )

    session = recording_async_session_factory()
    result = await raw_documents_service.verify_raw_document_source_srvc(raw_document, session)

    assert result.source_status == raw_documents_service.RAW_DOCUMENT_SOURCE_STATUS_CHANGED
    assert session.commit_calls == 1
