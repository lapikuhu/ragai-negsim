

def make_retriever(vector_store):
    """Create a langchain retriever from the specified vector store.
    Args:
        vector_store: The vector store instance to use for creating the retriever.
    Returns:
        A langchain retriever instance that can be used to retrieve relevant 
        documents based on queries.
    """

    retriever = vector_store.as_retriever(
        search_kwargs={"k": 4}
    )
    return retriever