from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings


# local imports
from core.config import settings

def hf_mini_l6_v2_embeddings():
    """Return HuggingFaceEmbeddings instance for MiniLM-L6-v2 model.
    Dimensionality: 384
    """
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        encode_kwargs={"normalize_embeddings": True},
    )

def hf_bge_base_embeddings():
    """Return HuggingFaceEmbeddings instance for BGE-base model.
    Dimensionality: 768"""
    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-large-zh-v1.5",
        encode_kwargs={"normalize_embeddings": True},
    )

def openai_text_embedding_3_small():
    """Return OpenAIEmbeddings instance for text-embedding-3-small model.
    Dimensionality: 1536
    """
    return OpenAIEmbeddings(
        model="text-embedding-3-small"
    )

def choose_embedding_model(model_name: str):
    """Return an instance of the specified embedding model.
    Args:
        model_name (str): The name of the embedding model to return. 
            Supported values are "mini_l6_v2", "bge_base", and "text_embedding_3_small".
    Returns:
        An instance of the specified embedding model.
    Raises:
        ValueError: If an unsupported model name is provided.
    """
    if model_name == "mini_l6_v2":
        return hf_mini_l6_v2_embeddings()
    elif model_name == "bge_base":
        return hf_bge_base_embeddings()
    elif model_name == "text_embedding_3_small":
        return openai_text_embedding_3_small()
    else:
        raise ValueError(f"Unsupported model name: {model_name}. Supported values are 'mini_l6_v2', 'bge_base', and 'text_embedding_3_small'.")