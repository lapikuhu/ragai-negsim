from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
import networkx as nx
from langchain_experimental.graph_transformers import LLMGraphTransformer
from val_schema import ENTITIES, RELATIONS, VALIDATION_SCHEMA

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
from llama_index.core.indices.property_graph import SimpleLLMPathExtractor
from llama_index.core.indices.property_graph import ImplicitPathExtractor
from llama_index.core.indices.property_graph import SchemaLLMPathExtractor


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



def get_free_form_kg(graph_llm) -> SimpleLLMPathExtractor:
    """
    Create a SimpleLLMPathExtractor instance for extracting knowledge graph
    paths from documents using a language model.
    Args:
        graph_llm: The language model to use for extracting knowledge graph paths.
    Returns:
        SimpleLLMPathExtractor: An instance of SimpleLLMPathExtractor.
    """
    kg_extractor = SimpleLLMPathExtractor(llm=graph_llm)
    return kg_extractor

def get_implicit_kg() -> ImplicitPathExtractor:
    """
    Create an ImplicitPathExtractor instance for extracting knowledge graph
    paths from documents using implicit methods.
    Args:
        None
    Returns:
        ImplicitPathExtractor: An instance of ImplicitPathExtractor.
    """
    kg_extractor = ImplicitPathExtractor()
    return kg_extractor

def get_schema_kg(
    graph_llm, 
    entities: list[str], 
    relations: list[str], 
    schema: dict,
    strict: bool = True
) -> SchemaLLMPathExtractor:
    """
    Create a SchemaLLMPathExtractor instance for extracting knowledge graph
    paths from documents using a language model and a specified schema.
    Args:
        graph_llm: The language model to use for extracting knowledge graph paths.
        entities (list[str]): A list of possible entities in the knowledge graph.
        relations (list[str]): A list of possible relations in the knowledge graph.
        schema (dict): The schema for validating the knowledge graph paths.
        strict (bool): If True, enforces strict validation against the schema.
    Returns:
        SchemaLLMPathExtractor: An instance of SchemaLLMPathExtractor.
    """
    kg_extractor = SchemaLLMPathExtractor(
        llm=graph_llm, 
        possible_entities=entities, 
        possible_relations=relations, 
        kg_validation_schema=schema,
        strict=strict,  # if false, allows values outside of spec
    )
    return kg_extractor
### ---------------------------------------------------------------- ###
