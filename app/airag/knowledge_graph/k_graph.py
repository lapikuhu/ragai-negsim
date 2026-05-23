from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
import networkx as nx
from langchain_experimental.graph_transformers import LLMGraphTransformer


# local imports
from core.config import settings
### ---------------------------------------------------------------- ###
### Using the LLMGraphTransformer to build a knowledge graph from documents
# Get the OpenAI API key from the settings
OPENAI_API_KEY = settings.OPENAI_API_KEY

LLM_MODEL   = "gpt-4o-mini"
graph_llm = ChatOpenAI(model=LLM_MODEL, temperature=0)
embedding_model = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=OPENAI_API_KEY)

graph_transformer = LLMGraphTransformer(llm=graph_llm)

def build_knowledge_graph(documents: list[Document]) -> nx.Graph:
    """
    Build a knowledge graph from a list of langchain Documents using the 
    LLMGraphTransformer.
    Args:
        documents (list[Document]): A list of langchain Document objects to
            use for building the knowledge graph.
    Returns:
        An nx.Graph object representing the knowledge graph constructed from 
            the input documents.
    """
    graph = graph_transformer.transform(documents)
    return graph
### ---------------------------------------------------------------- ###


### ---------------------------------------------------------------- ###
## -------------------- Neo4j Graph Database Setup ------------------ ##

from db.db import create_neo4j_graph_store
from llama_index.core import SimpleDirectoryReader, PropertyGraphIndex

neo4j_graph_store = create_neo4j_graph_store()

def build_graph_index(documents: list[Document],
                      graph_store,
                      graph_llm,
                      embedding_model,
                      kg_extractors) -> PropertyGraphIndex:
    """
    Build a PropertyGraphIndex from a list of langchain Documents and
    store it in the specified graph store.
    Args:
        documents (list[Document]): A list of langchain Document objects to
            use for building the property graph index.
        graph_store: The graph store where the property graph index will be 
            stored.
        graph_llm: The language model to use for processing the documents.
            embedding_model: The embedding model to use for generating document 
            embeddings.
        kg_extractors: The knowledge graph extractors to use for extracting 
            information from the documents.
    Returns:
        PropertyGraphIndex: The constructed property graph index.
    """
    index = PropertyGraphIndex.from_documents(
        documents=documents,
        property_graph_store=graph_store,
        llm=graph_llm,
        embed_model=embedding_model,
        kg_extractors=kg_extractors)
    return index
### ---------------------------------------------------------------- ###
