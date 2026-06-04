from fastapi import APIRouter, HTTPException, status

from core.dependencies import (
    AdminVectorStoreDep,
    Page,
    SessionDep,
    VectorStoreAdminDep,
)
from schemas.vector_stores_schemas import (
    VectorStoreBackend,
    VectorStoreConnectionUpdate,
    VectorStoreCreate,
    VectorStoreReadWithIds,
    VectorStoreUpdate,
)
from services import vector_stores_service

# Register the router with a prefix and tags for grouping in API docs
router = APIRouter(prefix="/vector-stores", tags=["vector-stores"])


def _raise_vector_store_service_error(exc: ValueError) -> None:
    """
    Raise an HTTPException with a 409 Conflict status code for vector store 
    service errors.
        Args:
            exc: The ValueError exception to convert.
        Raises:
            HTTPException: The HTTP exception with a 409 status code and the
            error detail.
    """
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    ) from exc

### ---------------------- VECTOR STORE CREATE --------------------- ###
@router.post(
    "/",
    response_model=VectorStoreReadWithIds,
    status_code=status.HTTP_201_CREATED,
)
async def create_vector_store(
    vector_store_data: VectorStoreCreate,
    session: SessionDep,
    _admin: VectorStoreAdminDep,
) -> VectorStoreReadWithIds:
    """Create a new vector store endpoint.
        Args:
            vector_store_data: The data to create the vector store with.
            session: The database session.
            _admin: The admin dependency.
        Returns:
            A VectorStoreReadWithIds object containing the created 
            vector store data and associated corpus index IDs.
    """
    try:
        return await vector_stores_service.create_vector_store_srvc(
            vector_store_data,
            session,
        )
    except ValueError as exc:
        _raise_vector_store_service_error(exc)

#### ----------------------- VECTOR STORE LIST --------------------- ###
@router.get(
    "/",
    response_model=list[VectorStoreReadWithIds],
    status_code=status.HTTP_200_OK,
)
async def list_vector_stores(
    session: SessionDep,
    _admin: VectorStoreAdminDep,
    page: Page,
    backend: VectorStoreBackend | None = None,
    has_indexes: bool | None = None,
) -> list[VectorStoreReadWithIds]:
    """
    List vector stores with optional filtering by backend and whether they 
    have associated corpus indices.
        Args:
            session: The database session.
            page: The pagination parameters.
            backend: Optional backend filter.
            has_indexes: Optional filter to include only vector stores with 
                or without corpus indices.
        Returns:
            A list of VectorStoreReadWithIds objects containing the vector 
            store data and associated corpus index IDs.
    """
    return await vector_stores_service.list_vector_stores_srvc(
        session=session,
        skip=page["skip"],
        limit=page["limit"],
        backend=backend,
        has_indexes=has_indexes,
    )

### ------------------------ VECTOR STORE GET ---------------------- ###
@router.get(
    "/{vector_store_id}",
    response_model=VectorStoreReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def get_vector_store(
    vector_store: AdminVectorStoreDep,
    session: SessionDep,
) -> VectorStoreReadWithIds:
    """
    Get a vector store by ID.
         Args:
            vector_store: The vector store to get (injected by dependency).
            session: The database session.
        Returns:
            A VectorStoreReadWithIds object containing the vector store
            data and associated corpus index IDs.
    """
    return await vector_stores_service.get_vector_store_srvc(vector_store, session)

### ----------------------- VECTOR STORE UPDATE -------------------- ###
@router.patch(
    "/{vector_store_id}",
    response_model=VectorStoreReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def update_vector_store(
    vector_store_data: VectorStoreUpdate,
    vector_store: AdminVectorStoreDep,
    session: SessionDep,
) -> VectorStoreReadWithIds:
    """
    Update a vector store by ID.
        Args:
            vector_store_data: The data to update the vector store with.
            vector_store: The vector store to update (injected by dependency).
            session: The database session.
        Returns:
            A VectorStoreReadWithIds object containing the updated vector store
            data and associated corpus index IDs.
    """
    try:
        return await vector_stores_service.update_vector_store_srvc(
            vector_store,
            vector_store_data,
            session,
        )
    except ValueError as exc:
        _raise_vector_store_service_error(exc)

### --------------------- VECTOR STORE CONNECTION UPDATE ------------------ ###
@router.patch(
    "/{vector_store_id}/connection",
    response_model=VectorStoreReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def update_vector_store_connection(
    connection_data: VectorStoreConnectionUpdate,
    vector_store: AdminVectorStoreDep,
    session: SessionDep,
) -> VectorStoreReadWithIds:
    """
    Update the connection details of a vector store by ID.
        Args:
            connection_data: The connection data to update the vector 
                store with.
            vector_store: The vector store to update (injected by dependency).
            session: The database session.
        Returns:
            A VectorStoreReadWithIds object containing the updated vector store
            data and associated corpus index IDs.
    """
    try:
        return await vector_stores_service.update_vector_store_connection_srvc(
            vector_store,
            connection_data,
            session,
        )
    except ValueError as exc:
        _raise_vector_store_service_error(exc)

### ----------------------- VECTOR STORE DELETE -------------------- ###
@router.delete(
    "/{vector_store_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_vector_store(
    vector_store: AdminVectorStoreDep,
    session: SessionDep,
) -> None:
    """
    Vector store delete endpoint.
        Args:
            vector_store: The vector store to delete (injected by dependency).
            session: The database session.
        Returns:
            None
        Raises:
            HTTPException: If the vector store has associated corpus indices.
    """
    try:
        await vector_stores_service.delete_vector_store_srvc(vector_store, session)
    except ValueError as exc:
        _raise_vector_store_service_error(exc)
