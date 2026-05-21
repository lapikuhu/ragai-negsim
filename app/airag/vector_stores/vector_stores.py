from langchain_chroma import Chroma
from langchain_core.documents import Document
from uuid import uuid4
from embeddings.embeddings import hf_mini_l6_v2_embeddings


chroma_vector_store = Chroma(
    collection_name="negotiation_corpus",
    embedding_function=hf_mini_l6_v2_embeddings,
    persist_directory="./chroma_db",
)

def store_docs_to_chroma_store(docs: list[Document], vector_store=chroma_vector_store):
    """Store a list of langchain Documents to the specified Chroma vector store.
    Args:
        docs (list[Document]): A list of langchain Document objects to store.
        vector_store: The vector store instance to use for storing the documents. 
            Defaults to chroma_vector_store.
    """
    ids = [str(uuid4()) for _ in docs]
    vector_store.add_documents(
        documents=docs,
        ids=ids,
    )
