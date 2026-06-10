from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# local imports
from app.models.corpus_indices import CorpusIndex
from app.models.vector_stores import VectorStore
from app.repositories.helpers import commit_and_refresh, commit_delete, utc_now
from app.schemas.vector_stores_schemas import (
    VectorStoreConnectionUpdate,
    VectorStoreCreate,
    VectorStoreReadWithIds,
    VectorStoreUpdate,
)

ALLOWED_VECTOR_STORE_BACKENDS = {"chroma", "faiss", "pgvector"}

def validate_vector_store_backend_config(
    backend: str,
    connection_uri: str | None = None,
    collection_name: str | None = None,
    table_name: str | None = None,
    path: str | None = None,
) -> None:
    """
    Validate that the vector store backend configuration is complete and consistent.
        Args:
            backend: The vector store backend type.
            connection_uri: The connection URI for the vector store 
                (if applicable).
            collection_name: The collection name for the vector store 
                (if applicable).
            table_name: The table name for the vector store (if applicable).
            path: The file system path for the vector store (if applicable).
        Raises:
            ValueError: If the configuration is invalid or incomplete for 
            the specified backend.
    """
    # TODO: Awkard validation. Does not validate connection_uri
    if backend not in ALLOWED_VECTOR_STORE_BACKENDS:
        raise ValueError(f"Unsupported vector store backend: {backend}")

    if backend == "chroma" and (not collection_name or not path):
        raise ValueError("Chroma vector stores require collection_name and path")

    if backend == "faiss" and not path:
        raise ValueError("FAISS vector stores require path")

    if backend == "pgvector" and not table_name:
        raise ValueError("PGVector stores require table_name")


def _merged_backend_config(
    vector_store: VectorStore,
    update_data: dict,
) -> dict[str, str | None]:
    return {
        "backend": update_data.get("backend", vector_store.backend),
        "connection_uri": update_data.get("connection_uri", vector_store.connection_uri),
        "collection_name": update_data.get("collection_name", vector_store.collection_name),
        "table_name": update_data.get("table_name", vector_store.table_name),
        "path": update_data.get("path", vector_store.path),
    }


async def has_corpus_indices(vector_store_id: int, session: AsyncSession) -> bool:
    """
    Check if a vector store has any associated corpus indices.
        Args:
            vector_store_id: The ID of the vector store.
            session: The database session.
        Returns:
            True if the vector store has associated corpus indices, 
            False otherwise.
    """
    result = await session.exec(
        select(CorpusIndex.id).where(CorpusIndex.vector_store_id == vector_store_id).limit(1)
    )
    return result.first() is not None


async def ensure_vector_store_unreferenced(
    vector_store: VectorStore,
    session: AsyncSession,
) -> None:
    """
    Ensure that a vector store is not referenced by any corpus indices.
        Args:
            vector_store: The vector store to check.
            session: The database session.
        Raises:
            ValueError: If the vector store is referenced by any corpus 
            indices.
    """
    if vector_store.id is None:
        raise ValueError("Vector store must be persisted before it can be modified")

    if await has_corpus_indices(vector_store.id, session):
        raise ValueError("Cannot modify vector store referenced by corpus indexes")


async def get_vector_store_by_id(
    vector_store_id: int,
    session: AsyncSession,
) -> VectorStore | None:
    """
    Get a vector store by its ID.
        Args:
            vector_store_id: The ID of the vector store.
            session: The database session.
        Returns:
            The vector store if found, None otherwise.
    """
    return await session.get(VectorStore, vector_store_id)


async def get_vector_store_by_name(
    name: str,
    session: AsyncSession,
) -> VectorStore | None:
    """
    Get a vector store by its name.
        Args:
            name: The name of the vector store.
            session: The database session.
        Returns:
            The vector store if found, None otherwise.
    """
    result = await session.exec(select(VectorStore).where(VectorStore.name == name))
    return result.first()


async def list_vector_stores(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    backend: str | None = None,
    has_indexes: bool | None = None,
) -> list[VectorStore]:
    """
    List vector stores with optional filtering by backend and whether they 
    have associated corpus indices.
        Args:
            session: The database session.
            skip: The number of records to skip.
            limit: The maximum number of records to return.
            backend: Optional backend filter.
            has_indexes: Optional filter to include only vector stores with 
            or without corpus indices.
        Returns:
            A list of vector stores matching the criteria.
    """
    statement = select(VectorStore)

    if backend is not None:
        statement = statement.where(VectorStore.backend == backend)
    if has_indexes is not None:
        index_subquery = select(CorpusIndex.vector_store_id).distinct()
        if has_indexes:
            statement = statement.where(VectorStore.id.in_(index_subquery))
        else:
            statement = statement.where(VectorStore.id.not_in(index_subquery))

    statement = statement.offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def get_vector_store_corpus_index_ids(
    vector_store_id: int,
    session: AsyncSession,
) -> list[int]:
    """
    Get the IDs of corpus indices associated with a vector store.
        Args:
            vector_store_id: The ID of the vector store.
            session: The database session.
        Returns:
            A list of corpus index IDs.
    """
    result = await session.exec(
        select(CorpusIndex.id).where(CorpusIndex.vector_store_id == vector_store_id)
    )
    return [corpus_index_id for corpus_index_id in result.all() if corpus_index_id is not None]


async def to_vector_store_read_with_ids(
    vector_store: VectorStore,
    session: AsyncSession,
) -> VectorStoreReadWithIds:
    """
    Convert a VectorStore to a VectorStoreReadWithIds, including associated 
    corpus index IDs.
        Args:
            vector_store: The vector store to convert.
            session: The database session.
        Returns:
            A VectorStoreReadWithIds instance.
    """
    return VectorStoreReadWithIds(
        **vector_store.model_dump(),
        corpus_index_ids=await get_vector_store_corpus_index_ids(vector_store.id, session),
    )


async def ensure_vector_store_name_available(
    name: str,
    session: AsyncSession,
    exclude_vector_store_id: int | None = None,
) -> None:
    """
    Ensure that a vector store name is available for use.
        Args:
            name: The vector store name to check.
            session: The database session.
            exclude_vector_store_id: Optional vector store ID to exclude from
                the check (useful for updates).
        Raises:
            ValueError: If the vector store name is already taken.
    """
    existing_vector_store = await get_vector_store_by_name(name, session)
    if existing_vector_store is None:
        return

    if exclude_vector_store_id is not None and existing_vector_store.id == exclude_vector_store_id:
        return

    raise ValueError("Vector store name already exists")


async def create_vector_store(
    vector_store_in: VectorStoreCreate,
    session: AsyncSession,
    embedding_dimensions: int,
) -> VectorStore:
    """
    Create a new vector store.
        Args:
            vector_store_in: The vector store data to create.
            session: The database session.
        Returns:
            The created VectorStore instance.
    """
    await ensure_vector_store_name_available(vector_store_in.name, session)
    validate_vector_store_backend_config(
        backend=vector_store_in.backend,
        connection_uri=vector_store_in.connection_uri,
        collection_name=vector_store_in.collection_name,
        table_name=vector_store_in.table_name,
        path=vector_store_in.path,
    )

    vector_store = VectorStore(
        **vector_store_in.model_dump(exclude={"embedding_model"}),
        embedding_dimensions=embedding_dimensions,
    )
    return await commit_and_refresh(session, vector_store)


async def update_vector_store(
    vector_store: VectorStore,
    vector_store_in: VectorStoreUpdate,
    session: AsyncSession,
) -> VectorStore:
    """
    Update an existing vector store.
        Args:
            vector_store: The vector store to update.
            vector_store_in: The vector store data to update.
            session: The database session.
        Returns:
            The updated VectorStore instance.
    """
    await ensure_vector_store_unreferenced(vector_store, session)
    update_data = vector_store_in.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] is not None:
        await ensure_vector_store_name_available(update_data["name"], session, vector_store.id)

    validate_vector_store_backend_config(**_merged_backend_config(vector_store, update_data))

    for field_name, value in update_data.items():
        setattr(vector_store, field_name, value)

    vector_store.last_updated = utc_now()
    return await commit_and_refresh(session, vector_store)


async def update_vector_store_connection(
    vector_store: VectorStore,
    connection_in: VectorStoreConnectionUpdate,
    session: AsyncSession,
) -> VectorStore:
    """
    Update the connection details of an existing vector store.
        Args:
            vector_store: The vector store to update.
            connection_in: The connection data to update.
            session: The database session.
        Returns:
            The updated VectorStore instance.
    """
    await ensure_vector_store_unreferenced(vector_store, session)
    update_data = connection_in.model_dump(exclude_unset=True)
    validate_vector_store_backend_config(**_merged_backend_config(vector_store, update_data))

    for field_name, value in update_data.items():
        setattr(vector_store, field_name, value)

    vector_store.last_updated = utc_now()
    return await commit_and_refresh(session, vector_store)


async def delete_vector_store(
    vector_store: VectorStore,
    session: AsyncSession,
) -> None:
    """
    Delete a vector store.
    Args:
        vector_store: The vector store to delete.
        session: The database session.
    Raises:
        ValueError: If the vector store is referenced by any corpus indices.
    """
    await ensure_vector_store_unreferenced(vector_store, session)
    await commit_delete(session, vector_store)