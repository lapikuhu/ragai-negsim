from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import (
    AdminCorpusIndexDep,
    CorpusIndexAdminDep,
    Page,
    SessionDep,
)
from app.schemas.corpus_indices_schemas import (
    CorpusIndexBuildComplete,
    CorpusIndexCopy,
    CorpusIndexCreate,
    CorpusIndexMetadataUpdate,
    CorpusIndexReadWithIds,
    CorpusIndexReadWithIndexedChunks,
    CorpusIndexStatusUpdate,
)
from app.services import corpus_indices_service

# Instantiate the router for corpus indices endpoints
router = APIRouter(prefix="/corpus-indices", tags=["corpus-indices"])


def _raise_corpus_index_service_error(exc: ValueError) -> None:
    """
    Helper function to raise appropriate HTTP exceptions based on the error 
    message from corpus index services.
    Args:
        exc (ValueError): the exception raised by the corpus index service
    Raises:
        HTTPException: the appropriate HTTP exception based on the error message
    """
    detail = str(exc)
    if detail in {
        "Corpus not found",
        "Vector store not found",
        "Chunking profile not found",
    }:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc

    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc

### ----------------------- CORPUS INDEX CREATE ---------------------###
@router.post(
    "/",
    response_model=CorpusIndexReadWithIds,
    status_code=status.HTTP_201_CREATED,
)
async def create_corpus_index(
    index_data: CorpusIndexCreate,
    session: SessionDep,
    _admin: CorpusIndexAdminDep,
) -> CorpusIndexReadWithIds:
    """
    Create a new corpus index endpoint.
    Args:
        index_data (CorpusIndexCreate): the data for the new corpus index
        session (AsyncSession): the database session
        _admin (CorpusIndexAdminDep): the admin dependency
    Returns:
        CorpusIndexReadWithIds: the created corpus index with IDs
    """
    try:
        return await corpus_indices_service.create_corpus_index_srvc(
            index_data,
            session,
        )
    except ValueError as exc:
        _raise_corpus_index_service_error(exc)

### ----------------------- CORPUS INDEX LIST -----------------------###
@router.get(
    "/",
    response_model=list[CorpusIndexReadWithIds],
    status_code=status.HTTP_200_OK,
)
async def list_corpus_indices(
    session: SessionDep,
    _admin: CorpusIndexAdminDep,
    page: Page,
    corpus_id: int | None = None,
    vector_store_id: int | None = None,
    chunking_profile_id: int | None = None,
    status: str | None = None,
    has_indexed_chunks: bool | None = None,
) -> list[CorpusIndexReadWithIds]:
    """
    List corpus indices endpoint.
    Args:
        session (AsyncSession): the database session
        _admin (CorpusIndexAdminDep): the admin dependency
        page (Page): the pagination parameters
        corpus_id (int | None): filter by corpus ID
        vector_store_id (int | None): filter by vector store ID
        chunking_profile_id (int | None): filter by chunking profile ID
        status (str | None): filter by status
        has_indexed_chunks (bool | None): filter by whether the index 
            has indexed chunks
    Returns:
        list[CorpusIndexReadWithIds]: the list of corpus indices with IDs
    """
    try:
        return await corpus_indices_service.list_corpus_indices_srvc(
            session=session,
            skip=page["skip"],
            limit=page["limit"],
            corpus_id=corpus_id,
            vector_store_id=vector_store_id,
            chunking_profile_id=chunking_profile_id,
            status=status,
            has_indexed_chunks=has_indexed_chunks,
        )
    except ValueError as exc:
        _raise_corpus_index_service_error(exc)


@router.get(
    "/{index_id}",
    response_model=CorpusIndexReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def get_corpus_index(
    index: AdminCorpusIndexDep,
    session: SessionDep,
) -> CorpusIndexReadWithIds:
    """
    Get a corpus index by ID endpoint.
    Args:
        index (AdminCorpusIndexDep): the corpus index dependency
        session (SessionDep): the database session
    Returns:
        CorpusIndexReadWithIds: the corpus index with IDs
    """
    return await corpus_indices_service.get_corpus_index_srvc(index, session)

### ---------------------- CORPUS INDEX GET BY ID -------------------###
@router.get(
    "/{index_id}/indexed-chunks",
    response_model=CorpusIndexReadWithIndexedChunks,
    status_code=status.HTTP_200_OK,
)
async def get_corpus_index_indexed_chunks(
    index: AdminCorpusIndexDep,
    session: SessionDep,
) -> CorpusIndexReadWithIndexedChunks:
    """
    Get a corpus index with its indexed chunks by ID endpoint.
    Args:
        index (AdminCorpusIndexDep): the corpus index dependency
        session (SessionDep): the database session
    Returns:
        CorpusIndexReadWithIndexedChunks: the corpus index with indexed 
        chunks
    """
    return await corpus_indices_service.get_corpus_index_detail_srvc(index, session)

### ----------------------- CORPUS INDEX UPDATE ---------------------###
@router.patch(
    "/{index_id}",
    response_model=CorpusIndexReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def update_corpus_index(
    index_data: CorpusIndexMetadataUpdate,
    index: AdminCorpusIndexDep,
    session: SessionDep,
) -> CorpusIndexReadWithIds:
    """
    Update a corpus index's metadata endpoint.
    Args:
        index_data (CorpusIndexMetadataUpdate): the metadata update data
        index (AdminCorpusIndexDep): the corpus index dependency
        session (SessionDep): the database session
    Returns:
        CorpusIndexReadWithIds: the updated corpus index with IDs
    """
    try:
        return await corpus_indices_service.update_corpus_index_srvc(
            index,
            index_data,
            session,
        )
    except ValueError as exc:
        _raise_corpus_index_service_error(exc)

### ------------------- CORPUS INDEX STATUS UPDATE ------------------###
@router.patch(
    "/{index_id}/status",
    response_model=CorpusIndexReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def update_corpus_index_status(
    status_data: CorpusIndexStatusUpdate,
    index: AdminCorpusIndexDep,
    session: SessionDep,
) -> CorpusIndexReadWithIds:
    """
    Update a corpus index's status endpoint.
    Args:
        status_data (CorpusIndexStatusUpdate): the status update data
        index (AdminCorpusIndexDep): the corpus index dependency
        session (SessionDep): the database session
    Returns:
        CorpusIndexReadWithIds: the updated corpus index with IDs
    """
    try:
        return await corpus_indices_service.update_corpus_index_status_srvc(
            index,
            status_data,
            session,
        )
    except ValueError as exc:
        _raise_corpus_index_service_error(exc)


###----------------- CORPUS INDEX MARK BUILD COMPLETE ---------------###
@router.post(
    "/{index_id}/build-complete",
    response_model=CorpusIndexReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def mark_corpus_index_built(
    build_data: CorpusIndexBuildComplete,
    index: AdminCorpusIndexDep,
    session: SessionDep,
) -> CorpusIndexReadWithIds:
    """
    Mark a corpus index as built endpoint.
    Args:
        build_data (CorpusIndexBuildComplete): the build completion data
        index (AdminCorpusIndexDep): the corpus index dependency
        session (SessionDep): the database session
    Returns:
        CorpusIndexReadWithIds: the updated corpus index with IDs
    """
    try:
        return await corpus_indices_service.mark_corpus_index_built_srvc(
            index,
            build_data,
            session,
        )
    except ValueError as exc:
        _raise_corpus_index_service_error(exc)

###------------------------ CORPUS INDEX COPY -----------------------###
@router.post(
    "/{index_id}/copy",
    response_model=CorpusIndexReadWithIds,
    status_code=status.HTTP_201_CREATED,
)
async def copy_corpus_index(
    copy_data: CorpusIndexCopy,
    source_index: AdminCorpusIndexDep,
    session: SessionDep,
) -> CorpusIndexReadWithIds:
    """
    Copy a corpus index endpoint.
    Args:
        copy_data (CorpusIndexCopy): the copy data
        source_index (AdminCorpusIndexDep): the source corpus index dependency
        session (SessionDep): the database session
    Returns:
        CorpusIndexReadWithIds: the copied corpus index with IDs
    """
    try:
        return await corpus_indices_service.copy_corpus_index_srvc(
            source_index,
            copy_data,
            session,
        )
    except ValueError as exc:
        _raise_corpus_index_service_error(exc)

###----------------------- CORPUS INDEX DELETE ----------------------###
@router.delete(
    "/{index_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_corpus_index(
    index: AdminCorpusIndexDep,
    session: SessionDep,
) -> None:
    """
    Delete a corpus index endpoint.
    Args:
        index (AdminCorpusIndexDep): the corpus index dependency
        session (SessionDep): the database session
    Returns:
        None
    """
    try:
        await corpus_indices_service.delete_corpus_index_srvc(index, session)
    except ValueError as exc:
        _raise_corpus_index_service_error(exc)
