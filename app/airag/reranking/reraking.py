from langchain_core.documents import Document
from sentence_transformers import CrossEncoder
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever


### ------------------- Cross-Encoder Reranking ------------------- ###
# Lightweight cross-encoder fine-tuned σε MS MARCO (~80MB, CPU-friendly)
cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def cross_encoder_rerank(question: str, 
                         docs: list[Document], 
                         top_k: int = 3):
    """
    Rerank retrieved documents using a cross-encoder model.
    Args:
        question (str): The query string to use for reranking.
        docs (list[Document]): A list of documents to be reranked.
        top_k (int, optional): The number of top documents to return. Defaults 
            to 3.
    Returns:
        A list of tuples containing the document and its corresponding score, 
            sorted by relevance.
    """
    pairs  = [(question, d.page_content) for d in docs]
    scores = cross_encoder.predict(pairs)
    sorted_docs_and_scores = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)[:top_k]
    return sorted_docs_and_scores

### ----------------------- COHERE Reranking ---------------------- ###

from core.config import settings
COHERE_API_KEY = settings.COHERE_API_KEY

def  make_cohere_reranker(base_retriever,
                          rerank_model: str = "rerank-english-v3.0", 
                          top_n: int = 3,
                          ):
    """Create a CohereRerank instance for reranking retrieved documents.
    Args:
        base_retriever: The retriever instance whose retrieved documents will 
            be reranked.
        model (str, optional): The name of the Cohere model to use for 
            reranking. Defaults to "rerank-english-v3.0".
        top_n (int, optional): The number of top documents to return after 
            reranking. Defaults to 3.
    Returns:
        A CohereRerank instance that can be used to rerank retrieved documents 
            based on their relevance to a given query.
    """

    if COHERE_API_KEY:
        from langchain_cohere import CohereRerank

        # Define the CohereRerank instance with the specified model and top_n
        compressor = CohereRerank(model=rerank_model, top_n=top_n)
        cohere_retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=base_retriever,   
    )
        return cohere_retriever
    else:
        raise ValueError("Cohere API key not found. Please set the COHERE_API_KEY environment variable.")

