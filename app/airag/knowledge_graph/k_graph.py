from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
import networkx as nx
from langchain_experimental.graph_transformers import LLMGraphTransformer
from val_schema import ENTITIES, RELATIONS, VALIDATION_SCHEMA

# local imports
from app.core.config import settings
### ---------------------------------------------------------------- ###

### Using the LLMGraphTransformer to build a knowledge graph from documents
# Get the OpenAI API key from the settings
OPENAI_API_KEY = settings.OPENAI_API_KEY

LLM_MODEL   = "gpt-4o-mini"
graph_llm = ChatOpenAI(model=LLM_MODEL, temperature=0)
embedding_model = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=OPENAI_API_KEY)

graph_transformer = LLMGraphTransformer(llm=graph_llm)

def create_graph_transformer(llm_model: str = LLM_MODEL, 
                            temperature: float = 0) -> LLMGraphTransformer:
    """
    Create an instance of LLMGraphTransformer with the specified language model and temperature.
    Args:
        llm_model (str): The language model to use for the graph transformer.
        temperature (float): The temperature setting for the language model.
    Returns:
        An instance of LLMGraphTransformer configured with the specified parameters.
    """
    graph_llm = ChatOpenAI(model=llm_model, temperature=temperature)
    graph_transformer = LLMGraphTransformer(llm=graph_llm)
    return graph_transformer

def build_knowledge_graph(graph_transformer: LLMGraphTransformer, 
                          documents: list[Document]) -> nx.Graph:
    """
    Build a knowledge graph from a list of langchain Documents using the 
    LLMGraphTransformer.
    Args:
        graph_transformer (LLMGraphTransformer): An instance of 
            LLMGraphTransformer to use for building the knowledge graph.
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

from app.db.db import create_neo4j_graph_store
from llama_index.core import SimpleDirectoryReader, PropertyGraphIndex
from llama_index.core.indices.property_graph import SimpleLLMPathExtractor
from llama_index.core.indices.property_graph import ImplicitPathExtractor
from llama_index.core.indices.property_graph import SchemaLLMPathExtractor
from llama_index.core.schema import TextNode
from llama_index.core import Document as LlamaDocument



def get_llama_docs_from_langchain_docs(langchain_documents: list[Document]) -> list[LlamaDocument]:
    """
    Convert a list of langchain Documents into a list of llama-index 
    Documents for use in building a property graph index.
    Args:
        langchain_documents (list[Document]): A list of langchain Document objects to 
            convert.
    Returns:
        A list of llama-index Document objects converted from the input 
            langchain Documents.
    """
    llama_docs = []
    for doc in langchain_documents:
        llama_doc = LlamaDocument.from_langchain_format(doc)
        llama_docs.append(llama_doc)
    return llama_docs

def get_nodes_from_documents(documents: list[Document]) -> list[dict]:
    """Extract nodes from a list of langchain Documents and format them 
    for insertion into a Neo4j graph store.
    Args:
        documents (list[Document]): A list of langchain Document objects to extract nodes from.
    Returns:
        list[dict]: A list of dictionaries representing the nodes extracted from the documents.
    """
    nodes = [
        TextNode(
            text=doc.page_content,
            metadata=doc.metadata,
            id_=f"{doc.metadata.get('source', 'unknown')}::chunk::{doc.metadata.get('chunk_index', i)}",
        )
        for i, doc in enumerate(documents)
    ]
    return nodes

neo4j_graph_store = create_neo4j_graph_store()

def build_graph_index_from_nodes(nodes: list[TextNode],
                      graph_store,
                      graph_llm,
                      embedding_model,
                      kg_extractors) -> PropertyGraphIndex:
    """
    Build a PropertyGraphIndex from a list of TextNode objects and
    store it in the specified graph store. This prevents the llama-index
    from re-chunking and re-processing the documents. Make sure your nodes
    are created with get_nodes_from_documents func. Only useful when we
    can isolate and the chunks on a db.
    Args:
        nodes: list of TextNode objects representing the nodes to be included 
        in the graph index.
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
    index = PropertyGraphIndex(
        nodes=nodes,
        property_graph_store=graph_store,
        llm=graph_llm,
        embed_model=embedding_model,
        kg_extractors=kg_extractors)
    return index

def build_graph_index_from_documents(documents: list[Document],
                    graph_store,
                    graph_llm,
                    embedding_model,
                    kg_extractors,
                    graphchunk: bool = False) -> PropertyGraphIndex:
    """
    Build a PropertyGraphIndex from a list of langchain Documents. 
    If graphchunk is False, the function will extract nodes from the documents 
    and build the graph index directly from those nodes. If graphchunk 
    is True, the function will convert the langchain Documents into 
    llama-index Documents and let the PropertyGraphIndex handle the chunking 
    and node creation internally.
    Args:
        documents: A list of langchain Document objects to be included in the 
            graph index.
        graph_store: The graph store where the property graph index will be 
            stored.
        graph_llm: The language model to use for processing the documents.
        embedding_model: The embedding model to use for generating document 
            embeddings.
        kg_extractors: The knowledge graph extractors to use for extracting 
            information from the documents.
        graphchunk: A boolean flag indicating whether to let the PropertyGraphIndex
            handle chunking and node creation internally (True) or to extract nodes
            from the documents and build the graph index directly from those nodes (False).
    Returns:
        PropertyGraphIndex: The constructed property graph index. 
    """
    if not graphchunk:
        nodes = get_nodes_from_documents(documents)
        index = build_graph_index_from_nodes(nodes, graph_store, graph_llm, embedding_model, kg_extractors)
    else:
        llama_docs = get_llama_docs_from_langchain_docs(documents)
        index = PropertyGraphIndex.from_documents(
        documents=llama_docs,
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
