from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings


# local imports
from vector_stores.vector_stores import chroma_vector_store

hf_mini_l6_v2_embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    encode_kwargs={"normalize_embeddings": True},
)

