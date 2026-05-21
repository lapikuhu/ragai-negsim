from langchain_chroma import Chroma
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from uuid import uuid4
from sqlalchemy import inspect, text
from langchain_postgres import PGEngine, PGVectorStore

# local imports
from embeddings.embeddings import choose_embedding_model
from core.config import settings
from app.db.db import engine
# add db import here for pgvectorstore

# Choose the embedding model to use for the vector store
embedding_model, model_dimensionality = choose_embedding_model("mini_l6_v2")


### -------- Chroma Vector Store Section -------- ###
def instantiate_chroma_vector_store():
    """Instantiate a Chroma vector store"""
    chroma_vector_store = Chroma(
    collection_name="negotiation_corpus",
    embedding_function=embedding_model,
    persist_directory="./chroma_db",
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
def instantiate_faiss_vector_store():
    """Instantiate an empty FAISS vector store"""
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

def load_faiss_vector_store(path: str = "./faiss_db"):
    """Load a persisted FAISS index from disk"""
    return FAISS.load_local(
        path,
        embeddings=embedding_model,
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
lang_pg_engine = PGEngine.from_engine(engine)
VECTOR_TABLE = "rag_chunks"
VECTOR_SIZE = model_dimensionality["dimensionality"]

# Create/init the vector table
async def init_vector_table() -> None:
    """Check if the vector table exists, and create it if it doesn't."""
    # Check if the vector table already exists
    async with engine.connect() as conn:
        exists = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table(VECTOR_TABLE)
        )
    if not exists:
        await lang_pg_engine.ainit_vectorstore_table(
            table_name=VECTOR_TABLE,
            vector_size=VECTOR_SIZE,
        )
# Create a PGVectorStore instance
async def get_vector_store() -> PGVectorStore:
    """Instantiate and return a PGVectorStore instance connected to the 
    specified table.
    Args:
        None
    Returns:
        A PGVectorStore instance connected to the specified table.
    """
    store = await PGVectorStore.create(
        engine=lang_pg_engine,
        table_name=VECTOR_TABLE,
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