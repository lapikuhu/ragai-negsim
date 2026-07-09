from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

from fastapi import UploadFile

from app.core.config import settings
from app.models.raw_documents import RawDocument
from app.models.users import User
from app.repositories.raw_documents_repo import (
    create_raw_document,
    get_raw_document_by_id,
    list_raw_document_corpora,
    list_raw_documents,
)
from app.schemas.raw_documents_schemas import RawDocumentCreate, RawDocumentCreateDb
from sqlmodel.ext.asyncio.session import AsyncSession

RAW_DOCUMENT_SOURCE_STATUS_AVAILABLE = "available"
RAW_DOCUMENT_SOURCE_STATUS_MISSING = "missing"
RAW_DOCUMENT_SOURCE_STATUS_CHANGED = "changed"
RAW_DOCUMENT_SOURCE_STATUS_UNVERIFIED = "unverified"
RAW_DOCUMENT_SOURCE_STATUS_ERROR = "error"


def _hash_bytes(file_bytes: bytes) -> str:
    """
    Hash the given bytes using SHA-256 and return the hexadecimal digest.
    Args:
        file_bytes: The bytes to hash.
    Returns:
        str: The hexadecimal digest of the SHA-256 hash.
    """
    return sha256(file_bytes).hexdigest()


def _to_utc_datetime(timestamp: float) -> datetime:
    """
    Convert a timestamp to a UTC datetime object.
    Args:
        timestamp: The timestamp to convert.
    Returns:
        datetime: The corresponding UTC datetime object.
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _normalize_upload_filename(filename: str) -> str:
    """
    Normalize the uploaded filename by removing unwanted characters and 
    ensuring it has a valid format.
    Args:
        filename: The original filename of the uploaded file.
    Returns:
        str: The normalized filename.
    Raises:
        ValueError: If the filename is empty or contains no readable 
        characters.
    """
    candidate = Path(filename).name.strip()
    if not candidate:
        raise ValueError("Uploaded file must have a filename")

    extension = Path(candidate).suffix.lower()
    stem = Path(candidate).stem.strip()
    cleaned_stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", stem).strip(" ._-")
    if not cleaned_stem:
        raise ValueError("Uploaded filename must contain readable characters")

    return f"{cleaned_stem}{extension}"


async def create_raw_document_srvc(
    raw_document_data: RawDocumentCreate,
    session: AsyncSession,
    current_user: User,
) -> RawDocument:
    """
    Service function to create a new raw document.
    Args:
        raw_document_data: The data for the raw document to be created.
        session: The database session to use for the operation.
        current_user: The user creating the raw document.
    Returns:
        The created RawDocument instance.
    """
    raw_document_in = RawDocumentCreateDb(
        **raw_document_data.model_dump(),
        uploaded_by_user_id=current_user.id,
    )
    return await create_raw_document(raw_document_in=raw_document_in, session=session)


async def verify_raw_document_source_srvc(
    raw_document: RawDocument,
    session: AsyncSession,
) -> RawDocument:
    """
    Verify the source of a raw document and update its status accordingly.
    Args:
        raw_document: The raw document to verify.
        session: The database session to use for the operation.
    Returns:
        The updated RawDocument instance.
    """
    source_file = Path(raw_document.source_path)
    try:
        if not source_file.exists():
            if raw_document.source_status != RAW_DOCUMENT_SOURCE_STATUS_MISSING:
                raw_document.source_status = RAW_DOCUMENT_SOURCE_STATUS_MISSING
                session.add(raw_document)
                await session.commit()
                await session.refresh(raw_document)
            return raw_document

        stat_result = source_file.stat()
        current_size = stat_result.st_size
        current_mtime = _to_utc_datetime(stat_result.st_mtime)
        current_hash = _hash_bytes(source_file.read_bytes())
        if raw_document.source_hash and current_hash != raw_document.source_hash:
            if raw_document.source_status != RAW_DOCUMENT_SOURCE_STATUS_CHANGED:
                raw_document.source_status = RAW_DOCUMENT_SOURCE_STATUS_CHANGED
                session.add(raw_document)
                await session.commit()
                await session.refresh(raw_document)
            return raw_document

        raw_document.source_hash = current_hash
        raw_document.source_size = current_size
        raw_document.source_mtime = current_mtime
        raw_document.source_status = RAW_DOCUMENT_SOURCE_STATUS_AVAILABLE
        session.add(raw_document)
        await session.commit()
        await session.refresh(raw_document)
        return raw_document
    except Exception:
        if raw_document.source_status != RAW_DOCUMENT_SOURCE_STATUS_ERROR:
            raw_document.source_status = RAW_DOCUMENT_SOURCE_STATUS_ERROR
            session.add(raw_document)
            await session.commit()
            await session.refresh(raw_document)
        return raw_document


async def create_uploaded_raw_document_srvc(
    *,
    name: str,
    description: str | None,
    document_title: str | None,
    document_author: str | None,
    document_year: int | None,
    corpus_ids: list[int],
    upload: UploadFile,
    session: AsyncSession,
    current_user: User,
) -> RawDocument:
    """
    Store an uploaded raw document on disk and persist its metadata.
    Args:
        name: The name of the raw document.
        description: An optional description of the raw document.
        document_title: An optional title of the document.
        document_author: An optional author of the document.
        document_year: An optional year of the document.
        corpus_ids: A list of corpus IDs associated with the raw document.
        upload: The uploaded file to store.
        session: The database session to use for the operation.
        current_user: The user uploading the raw document.
    Returns:
        The created RawDocument instance.
    Raises:
        ValueError: If the uploaded file is not a PDF, is empty, or if a
            document with the same name already exists.
    """
    original_name = upload.filename or ""
    extension = Path(original_name).suffix.lower()
    if extension != ".pdf":
        raise ValueError("Only PDF uploads are currently supported")
    
    # Check for invalid file signature
    file_bytes = await upload.read(4)
    # Reset the file pointer to the beginning of the file after reading the signature
    await upload.seek(0)
    if file_bytes != b"%PDF":
        raise ValueError("Uploaded file does not have a valid PDF signature")
    
    raw_docs_dir = Path(settings.RAW_DOCS_DIR)
    raw_docs_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = _normalize_upload_filename(original_name)
    stored_path = raw_docs_dir / stored_filename
    if stored_path.exists():
        raise ValueError(f"A stored source document named '{stored_filename}' already exists")

    file_bytes = await upload.read()
    if not file_bytes:
        raise ValueError("Uploaded file is empty")
    # Check if the uploaded file exceeds the maximum allowed size
    if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
        raise ValueError(f"Uploaded file exceeds the maximum allowed size of {settings.MAX_UPLOAD_SIZE} bytes")

    stored_path.write_bytes(file_bytes)
    stat_result = stored_path.stat()
    raw_document_in = RawDocumentCreate(
        name=name,
        description=description,
        document_title=document_title,
        document_author=document_author,
        document_year=document_year,
        source_path=str(stored_path),
        source_hash=_hash_bytes(file_bytes),
        source_size=len(file_bytes),
        source_mtime=_to_utc_datetime(stat_result.st_mtime),
        source_status=RAW_DOCUMENT_SOURCE_STATUS_AVAILABLE,
        corpus_ids=corpus_ids,
    )
    try:
        return await create_raw_document_srvc(raw_document_in, session, current_user)
    except Exception:
        if stored_path.exists():
            stored_path.unlink()
        raise


async def list_raw_documents_srvc(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 10,
    uploaded_by_user_id: int | None = None,
    corpus_id: int | None = None,
    name_contains: str | None = None,
) -> list[RawDocument]:
    """
    Service function to list raw documents with optional filters and pagination.
    Args:
        session: The database session to use for the query.
        skip: The number of records to skip for pagination.
        limit: The maximum number of records to return.
        uploaded_by_user_id: Optional filter to return documents uploaded by a specific user.
        corpus_id: Optional filter to return documents associated with a specific corpus.
        name_contains: Optional filter to return documents whose names contain a specific substring.
    Returns:
        A list of RawDocument instances matching the filters and pagination criteria.
    """
    raw_documents = await list_raw_documents(session, skip, limit, uploaded_by_user_id, corpus_id, name_contains)
    verified_documents = []
    for raw_document in raw_documents:
        verified_documents.append(await verify_raw_document_source_srvc(raw_document, session))
    return verified_documents


async def get_raw_document_by_id_srvc(
    session: AsyncSession,
    raw_document_id: int,
) -> RawDocument | None:
    """
    Service function to get a raw document by its ID.
    Args:
        session: The database session to use for the query.
        raw_document_id: The ID of the raw document to retrieve.
    Returns:
        The RawDocument instance if found, else None.
    """
    raw_document = await get_raw_document_by_id(raw_document_id, session)
    if raw_document is None:
        return None
    verified_document = await verify_raw_document_source_srvc(raw_document, session)
    object.__setattr__(
        verified_document,
        "associated_corpora",
        await list_raw_document_corpora(raw_document_id, session),
    )
    return verified_document
