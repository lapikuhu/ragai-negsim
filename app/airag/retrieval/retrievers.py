from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever

def make_dense_retriever(
    vector_store,
    k: int = 4,
    metadata_filter: dict | None = None,
):
    """Create a langchain retriever from the specified vector store.
    Args:
        vector_store: The vector store instance to use for creating the 
            retriever.
        k (int, optional): The number of top documents to retrieve. 
            Defaults to 4.
    Returns:
        A langchain retriever instance that can be used to retrieve relevant 
        documents based on queries.
    """

    search_kwargs = {"k": k}
    if metadata_filter:
        search_kwargs["filter"] = metadata_filter

    retriever = vector_store.as_retriever(search_kwargs=search_kwargs)
    return retriever
# TODO: Integrate the bm25 retriever for completeness
def make_bm25_retriever(documents: list[Document], k: int = 4):
    """Create a BM25Retriever from a list of langchain Documents.
    Args:
        documents (list[Document]): A list of langchain Document objects 
            to use for the BM25 retriever.
        k (int, optional): The number of top documents to retrieve. Defaults 
            to 4.
    Returns:
        A BM25Retriever instance that can be used to retrieve relevant 
        documents based on queries.
    """
    retriever = BM25Retriever.from_documents(
        documents=documents,
        k=k,
    )
    return retriever

def make_hybrid_retriever(vector_store,
                          documents: list[Document], 
                          k: int = 4,
                          w_dense: float = 0.5,
                          w_bm25: float = 0.5) -> EnsembleRetriever:
    """Create a hybrid EnsembleRetriever that combines a dense retriever from
        the specified vector store and a BM25 retriever from the provided 
        documents.
    Args:        
        vector_store: The vector store instance to use for creating the 
            dense retriever.
        documents (list[Document]): A list of langchain Document objects to 
            use for the BM25 retriever.
        k (int, optional): The number of top documents to retrieve from each 
            retriever. Defaults to 4.
        w_dense (float, optional): The weight to assign to the dense 
            retriever's scores in the ensemble. Defaults to 0.5.
        w_bm25 (float, optional): The weight to assign to the BM25 
            retriever's scores in the ensemble. Defaults to 0.5.
    Returns:
        An EnsembleRetriever instance that combines the dense retriever and 
            BM25 retriever, which can be used to retrieve relevant documents 
            based on queries.
    """
    dense_retriever = make_dense_retriever(vector_store, k=k)
    bm25_retriever = make_bm25_retriever(documents, k=k)
    hybrid_retriever = EnsembleRetriever(
        retrievers=[dense_retriever, bm25_retriever],
        weights=[w_dense, w_bm25],
    )
    return hybrid_retriever

def make_graph_retriever(graph_index, k: int = 3):
    """Create a retriever from a llama-index graph index.
    Args:
        graph_index: The graph index instance to use for creating the 
            retriever.
        k (int, optional): The number of top documents to retrieve. 
            Defaults to 3.
    Returns:
        A retriever instance that can be used to retrieve relevant 
        documents based on queries using the graph
        index.
    """
    retriever = graph_index.as_retriever(
        include_text=True,
        similarity_top_k=k,
    )
    return retriever
