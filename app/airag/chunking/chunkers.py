import os, re, uuid, time
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_experimental.text_splitter import SemanticChunker
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from pydantic import BaseModel, Field
from typing import List

### ---- Embed these in the config file later ----
#matryoshka_dims = [1536, 512, 256, 128, 64]
#embedding_model = "gpt-4o-mini"
#embeddings = OpenAIEmbeddings(model=embedding_model)
### -----------------------------------------------

def cos_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate the cosine similarity between two vectors."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))

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

    
### --- Move these to config later ---
embeddings = HuggingFaceEmbeddings(
model_name="sentence-transformers/all-MiniLM-L6-v2",
encode_kwargs={"normalize_embeddings": True},
)

def chunk_document_list_recursive(documents: list[Document],
                                chunk_size: int = 1000,
                                chunk_overlap: int = 200,
                                separators=["\n\n", "\n", " ", ""]) -> List[Document]:
    """Chunk a list of documents into smaller pieces using recursive character splitting.
    Args:
        documents (list[Document]): The input list of LangChain documents to chunk.
        chunk_size (int, optional): The maximum size of each chunk. Defaults to 1000.
        chunk_overlap (int, optional): The number of characters to overlap between chunks. Defaults to 200.
        separators (List[str], optional): The list of separators to use for splitting. Defaults to ["\n\n", "\n", " ", ""].
    Returns:
        List[Document]: A list of chunked LangChain documents.
    """
    all_chunks = []
    for doc in documents:
        chunks = chunk_document_recursive(
            document=doc,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators
        )
        all_chunks.extend(chunks)
    return all_chunks

def chunk_document_semantic(document: Document,
                            embeddings: HuggingFaceEmbeddings = embeddings, 
                            breakpoint_threshold_type: str = "percentile",
                            breakpoint_threshold_amount: int = 90,
                            buffer_size: int = 1) -> List[Document]:
    """Chunk a document into smaller pieces using semantic chunking.
    Simple wrapper around SemanticChunker.
    Args:
        document (Document): The input LangChain document to chunk.
        embeddings (HuggingFaceEmbeddings, optional): The embeddings model to 
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
                                 embeddings: HuggingFaceEmbeddings = embeddings,
                                 breakpoint_threshold_type: str = "percentile",
                                 breakpoint_threshold_amount: int = 90,
                                 buffer_size: int = 1) -> list[Document]:
    """Chunk a list of documents into smaller pieces using semantic chunking.
    Args:
        documents (list[Document]): The input list of LangChain documents to chunk.
        embeddings (HuggingFaceEmbeddings, optional): The embeddings model to use for semantic chunking. Defaults to HuggingFaceEmbeddings with "sentence-transformers/all-MiniLM-L6-v2".
        breakpoint_threshold_type (str, optional): The type of threshold to use for determining breakpoints. Defaults to "percentile".
        breakpoint_threshold_amount (int, optional): The amount for the breakpoint threshold. Defaults to 90.
        buffer_size (int, optional): The buffer size to use. Defaults to 1.
    Returns:
        list[Document]: A list of chunked LangChain documents with metadata preserved from the input documents.
    """
    all_chunks = []
    for doc in documents:
        chunks = chunk_document_semantic(
            document=doc,
            embeddings=embeddings,
            breakpoint_threshold_type=breakpoint_threshold_type,
            breakpoint_threshold_amount=breakpoint_threshold_amount,
            buffer_size=buffer_size,
        )
        all_chunks.extend(chunks)
    return all_chunks