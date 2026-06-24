from fastapi import APIRouter, status

from app.core.dependencies import DocumentChunkAdminDep, Page, SessionDep
from app.schemas.document_chunks_schemas import DocumentChunkListResponse
from app.services import document_chunks_service

# Instantiate the APIRouter with a prefix and tags for the document chunks routes
router = APIRouter(prefix="/document-chunks", tags=["document-chunks"])

### ----------------------DOCUMENT CHUNKS LIST---------------------- ###
@router.get(
    "/",
    response_model=DocumentChunkListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_document_chunks(
    session: SessionDep,
    _admin: DocumentChunkAdminDep,
    page: Page,
    raw_document_id: int | None = None,
    chunking_profile_id: int | None = None,
    has_indexed_chunks: bool | None = None,
) -> DocumentChunkListResponse:
    """
    List document chunks with optional filters and pagination.
        Args:
            session: The database session.
            _admin: Dependency to ensure the user has admin privileges.
            page: Pagination parameters.
            raw_document_id: Optional filter for raw document ID.
            chunking_profile_id: Optional filter for chunking profile ID.
            has_indexed_chunks: Optional filter for whether the chunk has 
                indexed chunks.
        Returns:
            A list of DocumentChunkAdminRead instances.
    """
    return await document_chunks_service.list_document_chunks_srvc(
        session=session,
        skip=page["skip"],
        limit=page["limit"],
        raw_document_id=raw_document_id,
        chunking_profile_id=chunking_profile_id,
        has_indexed_chunks=has_indexed_chunks,
    )
