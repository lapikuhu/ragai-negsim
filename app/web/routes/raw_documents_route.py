from services.raw_documents_service import(create_raw_document_srvc,
                                           list_raw_documents_srvc,
                                           get_raw_document_by_id_srvc,)
from services.ingestion_service import ingest_raw_document_srvc
from schemas.ingestion_schemas import RawDocumentIngestResult
from schemas.raw_documents_schemas import RawDocumentCreate
from models.raw_documents import RawDocument
from fastapi import APIRouter, HTTPException
from core.dependencies import (
    ChunkingProfileDep,
    IngestionOptionsDep,
    SessionDep,
    RawDocumentCreatorDep,
    WritableRawDocumentDep,
)

router = APIRouter(prefix="/raw-documents", tags=["Raw Documents"])

### ------------------ CREATE A NEW RAW DOCUMENT ------------------- ###
@router.post("/", response_model=RawDocument)
async def create_raw_document(raw_document_data: RawDocumentCreate, 
                              session: SessionDep,
                              current_user: RawDocumentCreatorDep) -> RawDocument:
    """
    Endpoint to create a new raw document.
    Args:
        raw_document_data: The data for the raw document to be created.
        session: The database session to use for the operation.
        current_user: The user creating the raw document.
    Returns:
        The created RawDocument instance.
    """
    # Unpack payload and add the uploaded_by_user_id from the current user
    return await create_raw_document_srvc(raw_document_data, session, current_user)

### ------------------ LIST RAW DOCUMENTS WITH FILTERS AND PAGINATION ------------------- ###
@router.get("/", response_model=list[RawDocument])
async def list_raw_documents(session: SessionDep,
                             skip: int = 0,
                             limit: int = 10,
                             uploaded_by_user_id: int | None = None,
                             corpus_id: int | None = None,
                             name_contains: str | None = None) -> list[RawDocument]:
    """
    Endpoint to list raw documents with optional filters and pagination.
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
    return await list_raw_documents_srvc(session, 
                                         skip, 
                                         limit, 
                                         uploaded_by_user_id, 
                                         corpus_id, 
                                         name_contains)

### ------------------ GET A RAW DOCUMENT BY ID ------------------- ###
@router.get("/{raw_document_id}", response_model=RawDocument)
async def get_raw_document_by_id(raw_document_id: int, session: SessionDep) -> RawDocument:
    """
    Endpoint to get a raw document by its ID.
    Args:
        raw_document_id: The ID of the raw document to retrieve.
        session: The database session to use for the query.
    Returns:
        The RawDocument instance if found, else raises a 404 HTTPException.
    """
    raw_document = await get_raw_document_by_id_srvc(session, raw_document_id)
    if not raw_document:
        raise HTTPException(status_code=404, detail="Raw document not found")
    return raw_document


### ------------------ INGEST A RAW DOCUMENT ------------------- ###
@router.post(
    "/{raw_document_id}/chunking-profiles/{profile_id}/ingest",
    response_model=RawDocumentIngestResult,
)
async def ingest_raw_document(
    raw_document: WritableRawDocumentDep,
    chunking_profile: ChunkingProfileDep,
    session: SessionDep,
    options: IngestionOptionsDep,
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
