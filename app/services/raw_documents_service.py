from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings
from app.models.raw_documents import RawDocument
from app.models.users import User
from app.schemas.raw_documents_schemas import RawDocumentCreate, RawDocumentCreateDb
from app.repositories.raw_documents_repo import (create_raw_document, 
                                             list_raw_documents, 
                                             get_raw_document_by_id,)

from sqlmodel.ext.asyncio.session import AsyncSession

async def create_raw_document_srvc(raw_document_data: RawDocumentCreate,
                                   session: AsyncSession,
                                   current_user: User) -> RawDocument:
    """
    Service function to create a new raw document.
    Args:
        raw_document_data: The data for the raw document to be created.
        session: The database session to use for the operation.
        current_user: The user creating the raw document.
    Returns:
        The created RawDocument instance.
    """
    # Ensure the uploaded_by_user_id is set to the current user's ID
    raw_document_in = RawDocumentCreateDb(
        **raw_document_data.model_dump(),
        uploaded_by_user_id=current_user.id,
    )
    return await create_raw_document(raw_document_in=raw_document_in, session=session)


async def create_uploaded_raw_document_srvc(
    *,
    name: str,
    description: str | None,
    corpus_ids: list[int],
    upload: UploadFile,
    session: AsyncSession,
    current_user: User,
) -> RawDocument:
    """
    Store an uploaded raw document on disk and persist its metadata.
    """
    original_name = upload.filename or ""
    extension = Path(original_name).suffix.lower()
    if extension != ".pdf":
        raise ValueError("Only PDF uploads are currently supported")

    raw_docs_dir = Path(settings.RAW_DOCS_DIR)
    raw_docs_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid4().hex}{extension}"
    stored_path = raw_docs_dir / stored_filename
    file_bytes = await upload.read()
    if not file_bytes:
        raise ValueError("Uploaded file is empty")

    stored_path.write_bytes(file_bytes)
    raw_document_in = RawDocumentCreate(
        name=name,
        description=description,
        path=str(stored_path),
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
    return await list_raw_documents(session, skip, limit, uploaded_by_user_id, corpus_id, name_contains)

async def get_raw_document_by_id_srvc(session: AsyncSession,
                                      raw_document_id: int) -> RawDocument | None:
    """
    Service function to get a raw document by its ID.
    Args:
        session: The database session to use for the query.
        raw_document_id: The ID of the raw document to retrieve.
    Returns:
        The RawDocument instance if found, else None.
    """
    return await get_raw_document_by_id(session, raw_document_id)
