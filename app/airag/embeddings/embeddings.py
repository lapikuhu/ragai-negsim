from typing import Literal, TypedDict

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings


# local imports
from core.config import settings
OPENAI_API_KEY = settings.OPENAI_API_KEY

EmbeddingModelName = Literal["mini-l6-v2", "bge-base", "text-embedding-3-small"]


class EmbeddingModelInfo(TypedDict):
    name: EmbeddingModelName
    provider: str
    display_name: str
    dimensionality: int
    normalized: bool

# TODO: Move this to a config file
SUPPORTED_EMBEDDING_MODELS: dict[str, EmbeddingModelInfo] = {
    "mini-l6-v2": {
        "name": "mini-l6-v2",
        "provider": "huggingface",
        "display_name": "Sentence Transformers all-MiniLM-L6-v2",
        "dimensionality": 384,
        "normalized": True,
    },
    "bge-base": {
        "name": "bge-base",
        "provider": "huggingface",
        "display_name": "BAAI bge-large-zh-v1.5",
        "dimensionality": 768,
        "normalized": True,
    },
    "text-embedding-3-small": {
        "name": "text-embedding-3-small",
        "provider": "openai",
        "display_name": "OpenAI text-embedding-3-small",
        "dimensionality": 1536,
        "normalized": False,
    },
}


def list_supported_embedding_models() -> list[EmbeddingModelInfo]:
    """
    Return a list of supported embedding models.
    Returns:
        list[EmbeddingModelInfo]: A list of supported embedding models with their metadata.
    """
    return list(SUPPORTED_EMBEDDING_MODELS.values())


def get_embedding_model_info(model_name: str) -> EmbeddingModelInfo:
    """
    Return the metadata for a specified embedding model.
    Args:
        model_name (str): The name of the embedding model to retrieve metadata for.
    Returns:
        EmbeddingModelInfo: The metadata for the specified embedding model.
    Raises:
        ValueError: If an unsupported model name is provided.
    """
    try:
        return SUPPORTED_EMBEDDING_MODELS[model_name]
    except KeyError as exc:
        supported = "', '".join(SUPPORTED_EMBEDDING_MODELS)
        raise ValueError(
            f"Unsupported model name: {model_name}. Supported values are '{supported}'."
        ) from exc

def hf_mini_l6_v2_embeddings() -> HuggingFaceEmbeddings:
    """Return HuggingFaceEmbeddings instance for MiniLM-L6-v2 model.
    Dimensionality: 384
    """
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        encode_kwargs={"normalize_embeddings": True},
    )

def hf_bge_base_embeddings() -> HuggingFaceEmbeddings:
    """Return HuggingFaceEmbeddings instance for BGE-base model.
    Dimensionality: 768"""
    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-large-zh-v1.5",
        encode_kwargs={"normalize_embeddings": True},
    )

def openai_text_embedding_3_small() -> OpenAIEmbeddings:
    """Return OpenAIEmbeddings instance for text-embedding-3-small model.
    Dimensionality: 1536
    """
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=OPENAI_API_KEY
    )

def choose_embedding_model(model_name: str) -> tuple[HuggingFaceEmbeddings, dict[str, int]] | tuple[OpenAIEmbeddings, dict[str, int]]:
    """Return an instance of the specified embedding model.
    Args:
        model_name (str): The name of the embedding model to return. 
            Supported values are "mini_l6_v2", "bge_base", and "text_embedding_3_small".
    Returns:
        A tuple containing an instance of the specified embedding model and a 
        dictionary with its dimensionality.
    Raises:
        ValueError: If an unsupported model name is provided.
    """
    model_info = get_embedding_model_info(model_name)
    metadata = {"dimensionality": model_info["dimensionality"]}

    if model_name == "mini-l6-v2":
        return hf_mini_l6_v2_embeddings(), metadata
    if model_name == "bge-base":
        return hf_bge_base_embeddings(), metadata
    if model_name == "text-embedding-3-small":
        return openai_text_embedding_3_small(), metadata

    raise ValueError(f"Unsupported model name: {model_name}")
