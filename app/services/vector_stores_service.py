from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.vector_stores import VectorStore
from app.repositories import vector_stores_repo
from app.schemas.vector_stores_schemas import (
    VectorStoreConnectionUpdate,
    VectorStoreCreate,
    VectorStoreReadWithIds,
    VectorStoreUpdate,
)


def _vector_store_create_payload(vector_store_data: VectorStoreCreate) -> VectorStoreCreate:
    from app.airag.embeddings.embeddings import get_embedding_model_info

    get_embedding_model_info(vector_store_data.embedding_model)
    return vector_store_data


def _vector_store_embedding_dimensions(vector_store_data: VectorStoreCreate) -> int:
    from app.airag.embeddings.embeddings import get_embedding_model_info

    embedding_info = get_embedding_model_info(vector_store_data.embedding_model)
    return embedding_info["dimensionality"]


async def _read_vector_store_with_ids(
    vector_store: VectorStore,
    session: AsyncSession,
) -> VectorStoreReadWithIds:
    """
    Read a VectorStore and include the IDs of associated corpus indices.
        Args:
            vector_store: The vector store to read.
            session: The database session.
        Returns:
            A VectorStoreReadWithIds object containing the vector store 
            data and associated corpus index IDs.
    """
    return await vector_stores_repo.to_vector_store_read_with_ids(vector_store, session)


async def create_vector_store_srvc(
    vector_store_data: VectorStoreCreate,
    session: AsyncSession,
) -> VectorStoreReadWithIds:
    """
    Create a new VectorStore and return it with associated corpus index IDs.
        Args:
            vector_store_data: The data for the vector store to create.
            session: The database session.
        Returns:
            A VectorStoreReadWithIds object containing the created vector store
            data and associated corpus index IDs.
    """
    vector_store = await vector_stores_repo.create_vector_store(
        _vector_store_create_payload(vector_store_data),
        session,
        embedding_dimensions=_vector_store_embedding_dimensions(vector_store_data),
    )
    return await _read_vector_store_with_ids(vector_store, session)


async def list_vector_stores_srvc(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    backend: str | None = None,
    has_indexes: bool | None = None,
) -> list[VectorStoreReadWithIds]:
    """
    List vector stores with optional filtering by backend and whether they have associated corpus indices.
        Args:
            session: The database session.
            skip: The number of records to skip.
            limit: The maximum number of records to return.
            backend: Optional backend filter.
            has_indexes: Optional filter to include only vector stores with or without corpus indices.
        Returns:
            A list of VectorStoreReadWithIds objects containing the vector store data and associated corpus index IDs.
    """
    vector_stores = await vector_stores_repo.list_vector_stores(
        session=session,
        skip=skip,
        limit=limit,
        backend=backend,
        has_indexes=has_indexes,
    )
    return [
        await _read_vector_store_with_ids(vector_store, session)
        for vector_store in vector_stores
    ]


async def get_vector_store_srvc(
    vector_store: VectorStore,
    session: AsyncSession,
) -> VectorStoreReadWithIds:
    """
    Get a VectorStore and include the IDs of associated corpus indices.
        Args:
            vector_store: The vector store to get.
            session: The database session.
        Returns:
            A VectorStoreReadWithIds object containing the vector store 
            data and associated corpus index IDs.
    """
    return await _read_vector_store_with_ids(vector_store, session)

# CHECK
async def update_vector_store_srvc(
    vector_store: VectorStore,
    vector_store_data: VectorStoreUpdate,
    session: AsyncSession,
) -> VectorStoreReadWithIds:
    """
    Update a VectorStore and return it with associated corpus index IDs.
        Args:
            vector_store: The vector store to update.
            vector_store_data: The data to update the vector store with.
            session: The database session.
        Returns:
            A VectorStoreReadWithIds object containing the updated vector store
            data and associated corpus index IDs.
    """
    updated_vector_store = await vector_stores_repo.update_vector_store(
        vector_store,
        vector_store_data,
        session,
    )
    return await _read_vector_store_with_ids(updated_vector_store, session)


async def update_vector_store_connection_srvc(
    vector_store: VectorStore,
    connection_data: VectorStoreConnectionUpdate,
    session: AsyncSession,
) -> VectorStoreReadWithIds:
    """
    Update the connection details of a VectorStore and return it with associated corpus index IDs.
        Args:
            vector_store: The vector store to update.
            connection_data: The connection data to update the vector store with.
            session: The database session.
        Returns:
            A VectorStoreReadWithIds object containing the updated vector store
            data and associated corpus index IDs.
    """
    updated_vector_store = await vector_stores_repo.update_vector_store_connection(
        vector_store,
        connection_data,
        session,
    )
    return await _read_vector_store_with_ids(updated_vector_store, session)


async def delete_vector_store_srvc(
    vector_store: VectorStore,
    session: AsyncSession,
) -> None:
    """
    Delete a VectorStore if it has no associated corpus indices.
        Args:
            vector_store: The vector store to delete.
            session: The database session.
        Raises:
            ValueError: If the vector store has associated corpus indices.
    """
    await vector_stores_repo.delete_vector_store(vector_store, session)
