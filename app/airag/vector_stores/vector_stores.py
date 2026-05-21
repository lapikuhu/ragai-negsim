from langchain_chroma import Chroma
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from uuid import uuid4
from embeddings.embeddings import choose_embedding_model

# Choose the embedding model to use for the vector store
embedding_model = choose_embedding_model("mini_l6_v2")


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