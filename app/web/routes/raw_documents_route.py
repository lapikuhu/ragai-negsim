from app.services.raw_documents_service import(create_uploaded_raw_document_srvc,
                                           list_raw_documents_srvc,
                                           get_raw_document_by_id_srvc,)
from app.services.ingestion_service import ingest_raw_document_srvc
from app.services.chunking_service import chunk_raw_document_srvc
from app.repositories import raw_documents_repo
from app.schemas.chunking_schemas import RawDocumentChunkResult
from app.schemas.ingestion_schemas import RawDocumentIngestResult
from app.schemas.raw_documents_schemas import (
    RawDocumentDetailRead,
    RawDocumentRead,
    RawDocumentUpdate,
)
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from app.core.dependencies import (
    ChunkingProfileDep,
    ChunkingExecutionOptionsDep,
    IngestionExecutionOptionsDep,
    SessionDep,
    RawDocumentCreatorDep,
    RawDocumentViewerDep,
    WritableRawDocumentDep,
)

router = APIRouter(prefix="/raw-documents", tags=["Raw Documents"])


def _serialize_raw_document(raw_document, fallback_username: str | None = None) -> RawDocumentRead:
    """
    Serialize a raw document object into a RawDocumentRead schema, 
    including the username of the uploader.
    Args:
        raw_document: The raw document object to serialize.
        fallback_username: Optional fallback username to use if the 
            uploader's username is not available.
    Returns:
        RawDocumentRead: The serialized raw document data.
    """
    payload = RawDocumentRead.model_validate(raw_document).model_dump()
    uploaded_by = getattr(raw_document, "uploaded_by", None)
    uploaded_by_username = getattr(uploaded_by, "username", None) or fallback_username
    payload["uploaded_by_username"] = uploaded_by_username
    return RawDocumentRead(**payload)


def _serialize_raw_document_detail(raw_document) -> RawDocumentDetailRead:
    """
    Serialize a raw document detail response with compact associated corpora.
    Args:
        raw_document: The raw document object to serialize.
    Returns:
        RawDocumentDetailRead: The serialized raw document detail data.
    """
    payload = RawDocumentDetailRead.model_validate(raw_document).model_dump()
    uploaded_by = getattr(raw_document, "uploaded_by", None)
    payload["uploaded_by_username"] = getattr(uploaded_by, "username", None)
    payload["associated_corpora"] = getattr(raw_document, "associated_corpora", [])
    return RawDocumentDetailRead(**payload)

### ------------------ CREATE A NEW RAW DOCUMENT ------------------- ###
@router.post("/", response_model=RawDocumentRead, status_code=status.HTTP_201_CREATED)
async def create_raw_document(
    *,
    name: str = Form(...),
    description: str | None = Form(default=None),
    document_title: str | None = Form(default=None),
    document_author: str | None = Form(default=None),
    document_year: int | None = Form(default=None),
    corpus_ids: list[int] = Form(default=[]),
    file: UploadFile = File(...),
    session: SessionDep,
    current_user: RawDocumentCreatorDep,
) -> RawDocumentRead:
    """
    Upload and register a new raw document.
    Args:
        name: Display name for the raw document.
        description: Optional description.
        document_title: Optional title of the document.
        document_author: Optional author of the document.
        document_year: Optional year of the document.
        corpus_ids: Optional corpora to link during creation.
        file: Uploaded PDF source file.
        session: The database session to use for the operation.
        current_user: The user creating the raw document.
    Returns:
        The created raw document metadata.
    """
    try:
        raw_document = await create_uploaded_raw_document_srvc(
            name=name,
            description=description,
            document_title=document_title,
            document_author=document_author,
            document_year=document_year,
            corpus_ids=corpus_ids,
            upload=file,
            session=session,
            current_user=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _serialize_raw_document(raw_document, fallback_username=current_user.username)

### ----------------- UPDATE RAW DOCUMENT METADATA ----------------- ###
@router.patch("/{raw_document_id}", response_model=RawDocumentDetailRead)
async def update_raw_document(
    raw_document: WritableRawDocumentDep,
    update_data: RawDocumentUpdate,
    session: SessionDep,
) -> RawDocumentDetailRead:
    """
    Update editable raw document metadata.
    Args:
        raw_document: The writable raw document dependency.
        update_data: The raw document fields to update.
        session: The database session to use for persistence.
    Returns:
        The updated raw document detail.
    """
    try:
        updated = await raw_documents_repo.update_raw_document(
            raw_document,
            update_data,
            session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _serialize_raw_document_detail(updated)

### ----------- LIST RAW DOCUMENTS WITH FILTERS AND PAGINATION ------------ ###
@router.get("/", response_model=list[RawDocumentRead])
async def list_raw_documents(session: SessionDep,
                             _current_user: RawDocumentViewerDep,
                             skip: int = 0,
                             limit: int = 10,
                             uploaded_by_user_id: int | None = None,
                             corpus_id: int | None = None,
                             name_contains: str | None = None) -> list[RawDocumentRead]:
    """
    Endpoint to list raw documents with optional filters and pagination.
    Args:
        session: The database session to use for the query.
        _current_user: The current user making the request, used for 
            permission checks.
        skip: The number of records to skip for pagination.
        limit: The maximum number of records to return.
        uploaded_by_user_id: Optional filter to return documents uploaded 
            by a specific user.
        corpus_id: Optional filter to return documents associated with a 
            specific corpus.
        name_contains: Optional filter to return documents whose names contain 
            a specific substring.
    Returns:
        A list of RawDocument instances matching the filters and pagination criteria.    
    """
    raw_documents = await list_raw_documents_srvc(session,
                                                  skip,
                                                  limit,
                                                  uploaded_by_user_id,
                                                  corpus_id,
                                                  name_contains)
    return [_serialize_raw_document(raw_document) for raw_document in raw_documents]

### ------------------ GET A RAW DOCUMENT BY ID ------------------- ###
@router.get("/{raw_document_id}", response_model=RawDocumentDetailRead)
async def get_raw_document_by_id(
    raw_document_id: int,
    session: SessionDep,
    _current_user: RawDocumentViewerDep,
) -> RawDocumentDetailRead:
    """
    Endpoint to get a raw document by its ID.
    Args:
        raw_document_id: The ID of the raw document to retrieve.
        session: The database session to use for the query.
        _current_user: The current user making the request, used for 
            permission checks.
    Returns:
        The RawDocument instance if found, else raises a 404 HTTPException.
    """
    raw_document = await get_raw_document_by_id_srvc(session, raw_document_id)
    if not raw_document:
        raise HTTPException(status_code=404, detail="Raw document not found")
    return _serialize_raw_document_detail(raw_document)


### ------------------ INGEST A RAW DOCUMENT ------------------- ###
@router.post(
    "/{raw_document_id}/chunking-profiles/{profile_id}/ingest",
    response_model=RawDocumentIngestResult,
)
async def ingest_raw_document(
    raw_document: WritableRawDocumentDep,
    chunking_profile: ChunkingProfileDep,
    session: SessionDep,
    options: IngestionExecutionOptionsDep,
) -> RawDocumentIngestResult:
    """
    Endpoint to ingest and parse a raw document into document chunks.
    Args:
        raw_document: The writable raw document to ingest.
        chunking_profile: The chunking profile to associate with created chunks.
        session: The database session to use for persistence.
        options: Query options controlling parsing and chunking.
    Returns:
        A summary of the created document chunks.
    """
    try:
        return await ingest_raw_document_srvc(
            raw_document=raw_document,
            chunking_profile=chunking_profile,
            session=session,
            options=options,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


### ------------------ CHUNK A RAW DOCUMENT ------------------- ###
@router.post(
    "/{raw_document_id}/chunking-profiles/{profile_id}/chunk",
    response_model=RawDocumentChunkResult,
)
async def chunk_raw_document(
    raw_document: WritableRawDocumentDep,
    chunking_profile: ChunkingProfileDep,
    session: SessionDep,
    options: ChunkingExecutionOptionsDep,
) -> RawDocumentChunkResult:
    """
    Endpoint to chunk an already parsed raw document into document chunks.
    Args:
        raw_document: The writable raw document to chunk.
        chunking_profile: The chunking profile to associate with created chunks.
        session: The database session to use for persistence.
        options: Query options controlling chunking behavior.
    Returns:
        A summary of the created or previewed document chunks.
    """
    try:
        return await chunk_raw_document_srvc(
            raw_document=raw_document,
            chunking_profile=chunking_profile,
            session=session,
            options=options,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
