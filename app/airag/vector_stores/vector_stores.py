from langchain_chroma import Chroma
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from uuid import uuid4
from sqlalchemy import inspect, text
from langchain_postgres import PGEngine, PGVectorStore

# local imports
from embeddings.embeddings import choose_embedding_model
from core.config import settings
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
    """Instantiate a Chroma vector store"""
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
    """Store a list of langchain Documents to the specified FAISS vector store.
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
    """Persist the FAISS index to disk"""
    vector_store.save_local(path)

def load_faiss_vector_store(embeddings, 
                            path: str = "./faiss_db") -> FAISS:
    """Load a persisted FAISS index from disk"""
    return FAISS.load_local(
        path,
        embeddings=embeddings,
        allow_dangerous_deserialization=True,
    )

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

# Bring it all together
async def instantiate_pgvector_store() -> PGVectorStore:
    """Enable pgvector extension, initialize the vector table if it doesn't 
    exist, and return a PGVectorStore instance connected to that table.
    Args:
        None
    Returns:
        A PGVectorStore instance connected to the specified table.
    """
    await enable_pgvector()
    await init_vector_table()
    vector_store = await get_vector_store()
    return vector_store