from fastapi import APIRouter, HTTPException, status as http_status

from app.core.dependencies import AdminDep, Page, SessionDep
from app.schemas.corpus_bm25_indices_schemas import CorpusBm25IndexMetadata
from app.services import corpus_bm25_indices_service

# Instantiate the APIRouter for corpus BM25 indices
router = APIRouter(
    prefix="/corpus-bm25-indices",
    tags=["corpus-bm25-indices"],
)

### ----------------------- BM25 INDEX LIST ------------------------ ###
@router.get(
    "/",
    response_model=list[CorpusBm25IndexMetadata],
    status_code=http_status.HTTP_200_OK,
)
async def list_corpus_bm25_indices(
    session: SessionDep,
    _admin: AdminDep,
    page: Page,
    corpus_id: int | None = None,
    chunking_profile_id: int | None = None,
    status: str | None = None,
) -> list[CorpusBm25IndexMetadata]:
    """
    List corpus BM25 indices with optional filters.

    Args:
        session: The database session dependency.
        _admin: The admin dependency.
        page: The pagination information.
        corpus_id: Optional corpus ID to filter by.
        chunking_profile_id: Optional chunking profile ID to filter by.
        status: Optional status to filter by.
    Returns:
        A list of CorpusBm25IndexMetadata objects matching the filters.
    """
    try:
        return await corpus_bm25_indices_service.list_corpus_bm25_indices_srvc(
            session=session,
            skip=page["skip"],
            limit=page["limit"],
            corpus_id=corpus_id,
            chunking_profile_id=chunking_profile_id,
            status=status,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
