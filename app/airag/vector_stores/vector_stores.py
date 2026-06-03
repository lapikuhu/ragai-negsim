from pathlib import Path
from uuid import uuid4

from langchain_chroma import Chroma
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from sqlalchemy import inspect, text
from langchain_postgres import PGEngine, PGVectorStore

# local imports
from airag.embeddings.embeddings import choose_embedding_model
from db.db import engine
# add db import here for pgvectorstore

# Choose the embedding model to use for the vector store
#embedding_model, model_dimensionality = choose_embedding_model("mini_l6_v2")


### -------- Chroma Vector Store Section -------- ###
def instantiate_chroma_vector_store(
        embedding_model,
        collection_name: str = "negotiation_corpus",
        persist_directory: str = "./chroma_db",
) -> Chroma:
    """
    Instantiate a Chroma vector store.
    Args:
        embedding_model: The embedding model instance to use for the vector store.
        collection_name: The name of the Chroma collection to use (default: 
            "negotiation_corpus").
        persist_directory: The directory where Chroma will persist its data
            (default: "./chroma_db").
    Returns:
        An instance of a Chroma vector store initialized with the specified
        embedding model, collection name, and persistence directory.
    """
    chroma_vector_store = Chroma(
    collection_name=collection_name,
    embedding_function=embedding_model,
    persist_directory=persist_directory,
    )
    return chroma_vector_store

def store_docs_to_chroma_store(docs: list[Document], vector_store):
    """Store a list of langchain Documents to the specified Chroma vector store.
    Args:
        docs (list[Document]): A list of langchain Document objects to store.
        vector_store: The vector store instance to use for storing the documents. 
    """
    ids = [str(uuid4()) for _ in docs]
    vector_store.add_documents(
        documents=docs,
        ids=ids,
    )


def add_docs_to_chroma_store(
        docs: list[Document],
        vector_store,
        ids: list[str],
) -> list[str]:
    """Store documents in Chroma with caller-provided vector IDs."""
    vector_store.add_documents(
        documents=docs,
        ids=ids,
    )
    if hasattr(vector_store, "persist"):
        vector_store.persist()
    return ids
### ----------------------------------------------- ###

### -------- FAISS Vector Store Section -------- ###
def instantiate_faiss_vector_store(embedding_model) -> FAISS:
    """
    Instantiate an empty FAISS vector store.
    Args:
        embedding_model: The embedding model instance to use for the vector store.
    Returns:
        An instance of a FAISS vector store initialized with the specified
        embedding model."""
    faiss_vector_store = FAISS.from_texts(
        texts=[""],
        embedding=embedding_model,
    )
    return faiss_vector_store

def store_docs_to_faiss_store(docs: list[Document], vector_store):
    """
    Store a list of langchain Documents to the specified FAISS vector store.
    Args:
        docs (list[Document]): A list of langchain Document objects to store.
        vector_store: The vector store instance to use for storing the documents.
    """
    ids = [str(uuid4()) for _ in docs]
    vector_store.add_documents(
        documents=docs,
        ids=ids,
    )

def save_faiss_vector_store(vector_store, path: str = "./faiss_db"):
    """
    Persist the FAISS index to disk
    Args:
        vector_store: The FAISS vector store instance to persist.
        path (str): The path to the directory where the FAISS index should be 
            saved.
    """
    vector_store.save_local(path)

def load_faiss_vector_store(embeddings, 
                            path: str = "./faiss_db") -> FAISS:
    """
    Load a persisted FAISS index from disk
    Args:
        embeddings: The embedding model instance to use for the FAISS index.
        path (str): The path to the directory where the FAISS index is stored.
    Returns:
        FAISS: The loaded FAISS vector store instance.
    """
    return FAISS.load_local(
        path,
        embeddings=embeddings,
        allow_dangerous_deserialization=True,
    )


def add_docs_to_faiss_store(
        docs: list[Document],
        embedding_model,
        path: str,
        ids: list[str],
) -> list[str]:
    """
    Create or update a local FAISS store and persist it to disk.
    Args:
        docs (list[Document]): A list of langchain Document objects to store.
        embedding_model: The embedding model instance to use for the FAISS index.
        path (str): The path to the directory where the FAISS index should be saved.
        ids (list[str]): A list of unique IDs for the documents.
    Returns:
        list[str]: The list of IDs for the stored documents.
    """
    index_path = Path(path)
    faiss_file = index_path / "index.faiss"
    pkl_file = index_path / "index.pkl"

    if faiss_file.exists() and pkl_file.exists():
        vector_store = load_faiss_vector_store(embedding_model, path)
        vector_store.add_documents(documents=docs, ids=ids)
    else:
        vector_store = FAISS.from_documents(
            documents=docs,
            embedding=embedding_model,
            ids=ids,
        )

    save_faiss_vector_store(vector_store, path)
    return ids

### ----------------------------------------------- ###

### -------------pgvectorstore Section------------- ###

# Enable pgvector
async def enable_pgvector() -> None:
    """Enable the pgvector extension in the PostgreSQL database.
    Args:
        None
    Returns:
        None
    """
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

# Create LangChain PGEngine from your existing async engine
def create_pg_engine(engine) -> PGEngine:
    """Create a LangChain PGEngine instance from the existing async SQLAlchemy engine.
    Args:
        engine: The existing async SQLAlchemy engine to use for the PGEngine.
    Returns:
        A PGEngine instance that can be used with LangChain's PGVectorStore."""
    return PGEngine.from_engine(engine)

def get_vector_size(embedding_model_name: str) -> int | None:
    """
    Get the vector dimensionality for the specified embedding model.
    Args:
        embedding_model_name (str): The name of the embedding model.
    Returns:
        int | None: The dimensionality of the embedding model's vectors, or 
        None if an error occurs.
    """
    try:
        _, model_dimensionality = choose_embedding_model(embedding_model_name)
        return model_dimensionality["dimensionality"]
    except ValueError as e:
        print(f"Error choosing embedding model: {e}")
    return None

#lang_pg_engine = PGEngine.from_engine(engine)
##VECTOR_TABLE = "rag_chunks"
#VECTOR_SIZE = model_dimensionality["dimensionality"]

# Create/init the vector table
async def init_vector_table(lang_pg_engine, 
                            vector_table_name: str,
                            embedding_model_name: str) -> None:
    """Check if the vector table exists, and create it if it doesn't.
    Args:
        lang_pg_engine: The LangChain PGEngine instance to use for database 
            operations.
        vector_table_name (str): The name of the vector table to check/create.
        embedding_model_name (str): The name of the embedding model to use for 
            determining vector size.
    Returns:
        None
    """
    # Get the vector size for the embedding model
    vector_size = get_vector_size(embedding_model_name)
    # Check if the vector table already exists
    async with engine.connect() as conn:
        exists = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table(vector_table_name)
        )
    if not exists:
        await lang_pg_engine.ainit_vectorstore_table(
            table_name=vector_table_name,
            vector_size=vector_size,
        )


async def init_vector_table_for_size(
        lang_pg_engine,
        vector_table_name: str,
        vector_size: int,
) -> None:
    """
    Initialize a pgvector table for a known vector size if missing.
    Args:
        lang_pg_engine: The LangChain PGEngine instance to use for database 
            operations.
        vector_table_name (str): The name of the vector table to check/create.
        vector_size (int): The size of the vectors to store in the table.
    Returns:
        None
    """
    async with engine.connect() as conn:
        exists = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table(vector_table_name)
        )
    if not exists:
        await lang_pg_engine.ainit_vectorstore_table( #CHECK
            table_name=vector_table_name,
            vector_size=vector_size,
        )
# Create a PGVectorStore instance
async def get_vector_store(lang_pg_engine, 
                           vector_table_name: str, 
                           embedding_model) -> PGVectorStore:
    """
    Instantiate and return a PGVectorStore instance connected to the 
    specified table.
    Args:
        lang_pg_engine: The LangChain PGEngine instance to use for database 
            operations.
        vector_table_name (str): The name of the vector table to connect to.
        embedding_model: The embedding model to use for the PGVectorStore.
    Returns:
        A PGVectorStore instance connected to the specified table.
    """
    store = await PGVectorStore.create(
        engine=lang_pg_engine,
        table_name=vector_table_name,
        embedding_service=embedding_model,
    )
    return store


async def add_docs_to_pgvector_store(
        docs: list[Document],
        embedding_model,
        table_name: str,
        vector_size: int,
        ids: list[str],
) -> list[str]:
    """
    Store documents in a pgvector table backed by the app database.
    Args:
        docs (list[Document]): A list of langchain Document objects to store.
        embedding_model: The embedding model instance to use for the PGVectorStore.
        table_name (str): The name of the vector table to store the documents in.
        vector_size (int): The size of the vectors to store in the table.
        ids (list[str]): A list of unique IDs for the documents.
    Returns:
        list[str]: The list of IDs for the stored documents.
    """
    await enable_pgvector()
    lang_pg_engine = create_pg_engine(engine)
    await init_vector_table_for_size(
        lang_pg_engine=lang_pg_engine,
        vector_table_name=table_name,
        vector_size=vector_size,
    )
    vector_store = await get_vector_store(
        lang_pg_engine=lang_pg_engine,
        vector_table_name=table_name,
        embedding_model=embedding_model,
    )
    if hasattr(vector_store, "aadd_documents"):
        await vector_store.aadd_documents(documents=docs, ids=ids)
    else:
        vector_store.add_documents(documents=docs, ids=ids)
    return ids


async def store_docs_to_vector_store(
        docs: list[Document],
        embedding_model,
        backend: str,
        ids: list[str],
        embedding_dimensions: int,
        collection_name: str | None = None,
        path: str | None = None,
        table_name: str | None = None,
) -> list[str]:
    """
    Store documents in one of the configured vector-store backends.
    Args:
        docs (list[Document]): A list of langchain Document objects to store.
        embedding_model: The embedding model instance to use for the vector store.
        backend (str): The name of the vector store backend to use ("chroma", 
            "faiss", or "pgvector").
        ids (list[str]): A list of unique IDs for the documents.
        embedding_dimensions (int): The dimensionality of the embedding vectors.
        collection_name (str | None): The name of the Chroma collection to use 
            (required if backend is "chroma").
        path (str | None): The path to the directory for local vector stores 
            (required if backend is "chroma" or "faiss").
        table_name (str | None): The name of the PGVector table to use 
            (required if backend is "pgvector").
    Returns:
        list[str]: The list of IDs for the stored documents.
    Raises:
        ValueError: If an unsupported backend is specified or if required 
        parameters are missing for the chosen backend.
    """
    if backend == "chroma":
        vector_store = instantiate_chroma_vector_store(
            embedding_model=embedding_model,
            collection_name=collection_name or "negotiation_corpus",
            persist_directory=path or "./chroma_db",
        )
        return add_docs_to_chroma_store(docs, vector_store, ids)

    if backend == "faiss":
        return add_docs_to_faiss_store(
            docs=docs,
            embedding_model=embedding_model,
            path=path or "./faiss_db",
            ids=ids,
        )

    if backend == "pgvector":
        if not table_name:
            raise ValueError("PGVector stores require table_name")
        return await add_docs_to_pgvector_store(
            docs=docs,
            embedding_model=embedding_model,
            table_name=table_name,
            vector_size=embedding_dimensions,
            ids=ids,
        )

    raise ValueError(f"Unsupported vector store backend: {backend}")

# Bring it all together
async def instantiate_pgvector_store( # CHECK FOR FULL FUNCTIONALITY
        vector_table_name: str,
        embedding_model,
        embedding_model_name: str,
) -> PGVectorStore:
    """
    Enable pgvector extension, initialize the vector table if it doesn't 
    exist, and return a PGVectorStore instance connected to that table.
    Args:
        vector_table_name (str): The name of the vector table to check/create and 
            connect to.
        embedding_model: The embedding model instance to use for the PGVectorStore.
        embedding_model_name (str): The name of the embedding model to use for 
            determining vector size when initializing the table.
    Returns:
        A PGVectorStore instance connected to the specified table.
    """
    await enable_pgvector()
    lang_pg_engine = create_pg_engine(engine)
    await init_vector_table(
        lang_pg_engine=lang_pg_engine,
        vector_table_name=vector_table_name,
        embedding_model_name=embedding_model_name,
    )
    vector_store = await get_vector_store(
        lang_pg_engine=lang_pg_engine,
        vector_table_name=vector_table_name,
        embedding_model=embedding_model,
    )
    return vector_store
