from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services import raw_documents_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
            corpus_ids=[],
            upload=upload,
            session=object(),
            current_user=SimpleNamespace(id=1),
        )


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
