from copy import deepcopy
from functools import lru_cache
from typing import Callable

from langchain_core.documents import Document
from langchain_classic.retrievers.contextual_compression import (
    ContextualCompressionRetriever,
)
from sentence_transformers import CrossEncoder

from app.core.config import settings

Reranker = Callable[[str, list[Document], int], list[Document]]

DEFAULT_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DEFAULT_COHERE_MODEL = "rerank-english-v3.0"


def is_reranker_available(name: str) -> bool:
    normalized_name = name.strip().lower()
    if normalized_name in {"cross_encoder", "none"}:
        return True
    if normalized_name == "cohere":
        return bool(getattr(settings, "COHERE_API_KEY", None))
    return False


def list_available_reranker_names() -> list[str]:
    names = ["cross_encoder"]
    if is_reranker_available("cohere"):
        names.append("cohere")
    names.append("none")
    return names


@lru_cache
def get_cross_encoder(cross_encoder_model_name: str = DEFAULT_CROSS_ENCODER_MODEL) -> CrossEncoder:
    """
    Create and cache the local cross-encoder only when first needed.
    Args:
        cross_encoder_model_name: The name of the cross-encoder model to load.
    Returns:
        An instance of the CrossEncoder model.
    """
    return CrossEncoder(cross_encoder_model_name)


def _clone_document(document: Document, score: float | None = None) -> Document:
    """
    Clone a Document object and optionally add a rerank score to its metadata.
    Args:
        document: The Document object to clone.
        score: An optional rerank score to add to the document's metadata.
    Returns:
        A new Document object with the same content and updated metadata.
    """
    metadata = deepcopy(document.metadata)
    if score is not None:
        metadata["rerank_score"] = float(score)
    return Document(page_content=document.page_content, metadata=metadata)


def cross_encoder_rerank(
    question: str,
    docs: list[Document],
    top_k: int = 3,
) -> list[Document]:
    """
    Rerank retrieved documents with a local cross-encoder model.
    Args:
        question: The user's question to use for reranking.
        docs: A list of Document objects to rerank.
        top_k: The maximum number of top documents to return.
    Returns:
        A list of reranked Document objects.
    """
    if not docs:
        return []

    pairs = [(question, document.page_content) for document in docs]
    scores = get_cross_encoder().predict(pairs)
    ranked = sorted(zip(docs, scores), key=lambda item: item[1], reverse=True)
    return [_clone_document(document, score) for document, score in ranked[:top_k]]


def none_rerank(_question: str, docs: list[Document], _top_k: int = 3) -> list[Document]:
    """
    Preserve the incoming retrieval order without truncation.
    Args:
        _question: The user's question (unused in this reranker).
        docs: A list of Document objects to preserve.
        _top_k: The maximum number of top documents to return (unused in this reranker).
    Returns:
        A list of Document objects in their original order.
    """
    return [_clone_document(document) for document in docs]


def make_cohere_document_reranker(
    rerank_model: str = DEFAULT_COHERE_MODEL,
) -> Reranker:
    """
    Create a document-list reranker backed by Cohere's rerank API.
    Args:
        rerank_model: The name of the Cohere rerank model to use.
    Returns:
        A callable that reranks a list of Document objects based on the 
        provided question.
    """
    cohere_api_key = getattr(settings, "COHERE_API_KEY", None)
    if not cohere_api_key:
        raise ValueError(
            "Cohere API key not found. Please set the COHERE_API_KEY environment variable."
        )

    from langchain_cohere import CohereRerank

    def rerank(question: str, docs: list[Document], top_k: int = 3) -> list[Document]:
        """
        Rerank a list of Document objects using Cohere's rerank API.
        Args:
            question: The user's question to use for reranking.
            docs: A list of Document objects to rerank.
            top_k: The maximum number of top documents to return.
        Returns:
            A list of reranked Document objects.
        """
        if not docs:
            return []

        compressor = CohereRerank(
            model=rerank_model,
            top_n=top_k,
            cohere_api_key=cohere_api_key,
        )
        compressed = compressor.compress_documents(docs, question)
        normalized_docs: list[Document] = []
        for document in compressed:
            score = document.metadata.get("relevance_score")
            normalized_docs.append(_clone_document(document, score))
        return normalized_docs

    return rerank


def choose_reranker(
    name: str = "cross_encoder",
    *,
    cohere_model: str = DEFAULT_COHERE_MODEL,
) -> Reranker:
    """
    Choose a normalized reranker backend by name.
    Args:
        name: The name of the reranker backend to use. Options are "cross_encoder",
            "cohere", or "none".
        cohere_model: The name of the Cohere rerank model to use if 
            "cohere" is selected.
    Returns:
        A callable that reranks a list of Document objects based on the 
        provided question.
    Raises:
        ValueError: If an unknown reranker name is provided.
    """
    normalized_name = name.strip().lower()
    if not is_reranker_available(normalized_name):
        if normalized_name == "cohere":
            raise ValueError(
                "Cohere reranker is unavailable because COHERE_API_KEY is not configured"
            )
        raise ValueError(f"Unknown reranker: {name}")
    if normalized_name == "cross_encoder":
        return cross_encoder_rerank
    if normalized_name == "cohere":
        return make_cohere_document_reranker(rerank_model=cohere_model)
    if normalized_name == "none":
        return none_rerank
    raise ValueError(f"Unknown reranker: {name}")


def make_cohere_reranker(
    base_retriever,
    rerank_model: str = DEFAULT_COHERE_MODEL,
    top_n: int = 3,
):
    """
    Create a Cohere ContextualCompressionRetriever for existing callers.
    Args:
        base_retriever: The base retriever to wrap with the Cohere reranker.
        rerank_model: The name of the Cohere rerank model to use.
        top_n: The maximum number of top documents to return after reranking.
    Returns:
        An instance of ContextualCompressionRetriever that reranks 
        documents using Cohere.
    Raises:
        ValueError: If the COHERE_API_KEY environment variable is not set.
    """
    cohere_api_key = getattr(settings, "COHERE_API_KEY", None)
    if not cohere_api_key:
        raise ValueError(
            "Cohere API key not found. Please set the COHERE_API_KEY environment variable."
        )

    from langchain_cohere import CohereRerank

    compressor = CohereRerank(
        model=rerank_model,
        top_n=top_n,
        cohere_api_key=cohere_api_key,
    )
    return ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=base_retriever,
    )
