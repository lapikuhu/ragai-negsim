from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.schemas.raw_documents_schemas import RawDocumentCreate, RawDocumentUpdate
from app.services import raw_documents_service
from app.web.routes import raw_documents_route


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_raw_document_metadata_accepts_valid_date_and_normalizes_blanks():
    raw_document = RawDocumentCreate(
        name="brief",
        description=None,
        source_path="brief.pdf",
        document_title="  Negotiation Brief  ",
        document_author="  Ada Lovelace  ",
        document_date="05-07-2026",
    )

    assert raw_document.document_title == "Negotiation Brief"
    assert raw_document.document_author == "Ada Lovelace"
    assert raw_document.document_date == "05-07-2026"

    update = RawDocumentUpdate(
        document_title=" ",
        document_author="",
        document_date=None,
    )

    assert update.document_title is None
    assert update.document_author is None
    assert update.document_date is None


@pytest.mark.parametrize("document_date", ["2026-07-05", "05/07/2026", "31-02-2026"])
def test_raw_document_metadata_rejects_invalid_document_date(document_date):
    with pytest.raises(ValueError):
        RawDocumentCreate(
            name="brief",
            description=None,
            source_path="brief.pdf",
            document_date=document_date,
        )


@pytest.mark.asyncio
async def test_create_uploaded_raw_document_rejects_duplicate_filename(tmp_path, monkeypatch):
    source_dir = tmp_path / "raw_docs_store"
    source_dir.mkdir()
    existing_file = source_dir / "brief.pdf"
    existing_file.write_bytes(b"%PDF-1.4\n%%EOF")

    monkeypatch.setattr(raw_documents_service.settings, "RAW_DOCS_DIR", str(source_dir))

    upload = SimpleNamespace(filename="brief.pdf", read=lambda: None)

    async def fake_read():
        return b"%PDF-1.4\n%%EOF"

    upload.read = fake_read

    with pytest.raises(ValueError, match="already exists"):
        await raw_documents_service.create_uploaded_raw_document_srvc(
            name="brief",
            description=None,
            document_title=None,
            document_author=None,
            document_date=None,
            corpus_ids=[],
            upload=upload,
            session=object(),
            current_user=SimpleNamespace(id=1),
        )


@pytest.mark.asyncio
async def test_create_raw_document_route_forwards_bibliographic_metadata(monkeypatch):
    captured = {}
    created = SimpleNamespace(
        id=21,
        name="alpha brief",
        description="Uploaded for testing",
        document_title="Negotiation Brief",
        document_author="Ada Lovelace",
        document_date="05-07-2026",
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
        document_date="05-07-2026",
        corpus_ids=[],
        file=SimpleNamespace(filename="alpha.pdf"),
        session=object(),
        current_user=SimpleNamespace(id=1, username="teacher"),
    )

    assert captured["document_title"] == "Negotiation Brief"
    assert captured["document_author"] == "Ada Lovelace"
    assert captured["document_date"] == "05-07-2026"
    assert result.document_title == "Negotiation Brief"
    assert result.document_author == "Ada Lovelace"
    assert result.document_date == "05-07-2026"


@pytest.mark.asyncio
async def test_update_raw_document_route_updates_bibliographic_metadata(monkeypatch):
    captured = {}
    raw_document = SimpleNamespace(id=21)
    updated = SimpleNamespace(
        id=21,
        name="alpha brief",
        description="Uploaded for testing",
        document_title="Updated title",
        document_author="Updated author",
        document_date="06-07-2026",
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
            document_date="06-07-2026",
        ),
        session=object(),
    )

    assert captured["raw_document"] is raw_document
    assert captured["update_data"].document_title == "Updated title"
    assert captured["update_data"].document_author == "Updated author"
    assert captured["update_data"].document_date == "06-07-2026"
    assert result.document_title == "Updated title"
    assert result.document_author == "Updated author"
    assert result.document_date == "06-07-2026"


@pytest.mark.asyncio
async def test_update_raw_document_route_maps_validation_error_to_conflict(monkeypatch):
    async def fake_update_raw_document(*_args, **_kwargs):
        raise ValueError("bad metadata")

    monkeypatch.setattr(raw_documents_route.raw_documents_repo, "update_raw_document", fake_update_raw_document)

    with pytest.raises(HTTPException) as exc_info:
        await raw_documents_route.update_raw_document(
            raw_document=SimpleNamespace(id=21),
            update_data=RawDocumentUpdate(document_date="05-07-2026"),
            session=object(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "bad metadata"


@pytest.mark.asyncio
async def test_verify_raw_document_source_marks_missing(tmp_path):
    raw_document = SimpleNamespace(
        source_path=str(tmp_path / "missing.pdf"),
        source_hash="hash",
        source_size=10,
        source_mtime=_now(),
        source_status="available",
    )

    class FakeSession:
        def __init__(self):
            self.added = []
            self.commit_calls = 0
            self.refresh_calls = 0

        def add(self, item):
            self.added.append(item)

        async def commit(self):
            self.commit_calls += 1

        async def refresh(self, item):
            self.refresh_calls += 1

    session = FakeSession()
    result = await raw_documents_service.verify_raw_document_source_srvc(raw_document, session)

    assert result.source_status == raw_documents_service.RAW_DOCUMENT_SOURCE_STATUS_MISSING
    assert session.commit_calls == 1


@pytest.mark.asyncio
async def test_verify_raw_document_source_marks_changed_when_hash_differs(tmp_path):
    source_file = tmp_path / "changed.pdf"
    source_file.write_bytes(b"new-bytes")
    raw_document = SimpleNamespace(
        source_path=str(source_file),
        source_hash="old-hash",
        source_size=9,
        source_mtime=_now(),
        source_status="available",
    )

    class FakeSession:
        def __init__(self):
            self.commit_calls = 0

        def add(self, item):
            return None

        async def commit(self):
            self.commit_calls += 1

        async def refresh(self, item):
            return None

    session = FakeSession()
    result = await raw_documents_service.verify_raw_document_source_srvc(raw_document, session)

    assert result.source_status == raw_documents_service.RAW_DOCUMENT_SOURCE_STATUS_CHANGED
    assert session.commit_calls == 1
