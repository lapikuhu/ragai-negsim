from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings

def chunk_document_recursive(document: Document, 
                             chunk_size: int = 1000, 
                             chunk_overlap: int = 200,
                             separators=["\n\n", "\n", " ", ""]) -> List[Document]:
    """Chunk a document into smaller pieces using recursive character splitting.
    Simple wrapper around RecursiveCharacterTextSplitter.
    Preserves metadata from the input document in each chunk.
    Args:
        document (Document): The input LangChain document to chunk.
        chunk_size (int, optional): The maximum size of each chunk. Defaults 
            to 1000.
        chunk_overlap (int, optional): The number of characters to overlap 
            between chunks. Defaults to 200.
        separators (List[str], optional): The list of separators to use for 
            splitting. Defaults to ["\n\n", "\n", " ", ""].
    Returns:
        List[Document]: A list of chunked LangChain documents.    
    """
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, 
                                                   chunk_overlap=chunk_overlap,
                                                   separators=separators)
    chunks = text_splitter.split_documents([document])
    return chunks

    
_default_embeddings: Embeddings | None = None


def get_default_embeddings() -> Embeddings:
    """
    Get the default embeddings model instance, initializing it if it 
    hasn't been already.
    Returns:
        Embeddings: The default embeddings model instance.
    """
    from langchain_huggingface import HuggingFaceEmbeddings

    global _default_embeddings
    if _default_embeddings is None:
        _default_embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            encode_kwargs={"normalize_embeddings": True},
        )
    return _default_embeddings

def chunk_document_list_recursive(documents: list[Document],
                                chunk_size: int = 1000,
                                chunk_overlap: int = 200,
                                separators=["\n\n", "\n", " ", ""]) -> List[Document]:
    """Chunk a list of documents into smaller pieces using recursive character splitting.
    Args:
        documents (list[Document]): The input list of LangChain documents 
            to chunk.
        chunk_size (int, optional): The maximum size of each chunk. 
            Defaults to 1000.
        chunk_overlap (int, optional): The number of characters to overlap 
            between chunks. Defaults to 200.
        separators (List[str], optional): The list of separators to use 
            for splitting. Defaults to ["\n\n", "\n", " ", ""].
    Returns:
        List[Document]: A list of chunked LangChain documents.
    """
    if separators is None:
        separators = ["\n\n", "\n", " ", ""]

    all_chunks = []

    text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
        )
    
    for doc_index, doc in enumerate(documents):
        chunks = text_splitter.split_documents([doc])
        # Add metadata to each chunk to keep track of the original document 
        # and chunk index.
        for chunk_index, chunk in enumerate(chunks):
            chunk.metadata["parent_doc_index"] = doc_index
            chunk.metadata["chunk_index"] = chunk_index

        all_chunks.extend(chunks)

    return all_chunks

def chunk_document_semantic(document: Document,
                            embeddings: Embeddings | None = None, 
                            breakpoint_threshold_type: str = "percentile",
                            breakpoint_threshold_amount: int = 90,
                            buffer_size: int = 1) -> List[Document]:
    """Chunk a document into smaller pieces using semantic chunking.
    Simple wrapper around SemanticChunker.
    Args:
        document (Document): The input LangChain document to chunk.
        embeddings (Embeddings, optional): The embeddings model to 
            use for semantic chunking. Defaults to HuggingFaceEmbeddings with 
            "sentence-transformers/all-MiniLM-L6-v2".
        breakpoint_threshold_type (str, optional): The type of threshold to use 
            for determining breakpoints. Defaults to "percentile".
        breakpoint_threshold_amount (int, optional): The amount for the breakpoint 
            threshold. Defaults to 90.
        buffer_size (int, optional): The buffer size to use. Defaults to 1.
    Returns:
        List[Document]: A list of chunked LangChain documents with metadata
        preserved from the input document.
    """
    if embeddings is None:
        embeddings = get_default_embeddings()

    from langchain_experimental.text_splitter import SemanticChunker

    # Use the experimental langchain SemanticChunker:
    splitter = SemanticChunker(
    embeddings,
    breakpoint_threshold_type=breakpoint_threshold_type,
    breakpoint_threshold_amount=breakpoint_threshold_amount,
    buffer_size=buffer_size
)
    
    chunks = splitter.split_documents([document])
    return chunks

def chunk_document_list_semantic(documents: list[Document],
                                 embeddings: Embeddings | None = None,
                                 breakpoint_threshold_type: str = "percentile",
                                 breakpoint_threshold_amount: int = 90,
                                 buffer_size: int = 1) -> list[Document]:
    """Chunk a list of documents into smaller pieces using semantic chunking.
    Args:
        documents (list[Document]): The input list of LangChain documents to chunk.
        embeddings (Embeddings, optional): The embeddings model to use for 
            semantic chunking. Defaults to HuggingFaceEmbeddings with 
            "sentence-transformers/all-MiniLM-L6-v2".
        breakpoint_threshold_type (str, optional): The type of threshold to 
            use for determining breakpoints. Defaults to "percentile".
        breakpoint_threshold_amount (int, optional): The amount for the 
            breakpoint threshold. Defaults to 90.
        buffer_size (int, optional): The buffer size to use. Defaults to 1.
    Returns:
        list[Document]: A list of chunked LangChain documents with metadata preserved from the input documents.
    """
    if embeddings is None:
        embeddings = get_default_embeddings()

    from langchain_experimental.text_splitter import SemanticChunker

    all_chunks = []
    
    for doc in documents:
        splitter = SemanticChunker(
            embeddings,
            breakpoint_threshold_type=breakpoint_threshold_type,
            breakpoint_threshold_amount=breakpoint_threshold_amount,
            buffer_size=buffer_size,
        )
        chunks = splitter.split_documents([doc])
        all_chunks.extend(chunks)
    return all_chunks

def chunk_document_list_hybrid(documents: list[Document],
                                embeddings: Embeddings | None = None,
                                breakpoint_threshold_type: str = "percentile",
                                breakpoint_threshold_amount: int = 90,
                                buffer_size: int = 1,
                                chunk_size: int = 1000,
                                chunk_overlap: int = 200,
                                separators: list[str] = ["\n\n", "\n", " ", ""]) -> list[Document]:
    """Chunk a list of documents into smaller pieces using a hybrid approach.
    Args:
        documents (list[Document]): The input list of LangChain documents 
            to chunk.
        embeddings (Embeddings, optional): The embeddings model to use for 
            semantic chunking. Defaults to HuggingFaceEmbeddings with 
            "sentence-transformers/all-MiniLM-L6-v2".
        breakpoint_threshold_type (str, optional): The type of threshold to 
            use for determining breakpoints. Defaults to "percentile".
        breakpoint_threshold_amount (int, optional): The amount for the 
            breakpoint threshold. Defaults to 90.
        buffer_size (int, optional): The buffer size to use. Defaults to 1.
        chunk_size (int, optional): The maximum size of each chunk. 
            Defaults to 1000.
        chunk_overlap (int, optional): The number of characters to overlap 
            between chunks. Defaults to 200.
        separators (list[str], optional): The list of separators to use 
            for splitting. Defaults to ["\n\n", "\n", " ", ""].
    Returns:
        list[Document]: A list of chunked LangChain documents with metadata 
        preserved from the input documents.
    """

    # First do semantic chunking
    semantic_chunks = chunk_document_list_semantic(
        documents,
        embeddings=embeddings,
        breakpoint_threshold_type=breakpoint_threshold_type,
        breakpoint_threshold_amount=breakpoint_threshold_amount,
        buffer_size=buffer_size
    )
    # Then do recursive character-based chunking on the semantic chunks
    all_chunks = chunk_document_list_recursive(
        semantic_chunks,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators
    )
    return all_chunks