from collections import defaultdict
from typing import Any, Sequence

from llama_index.core import PropertyGraphIndex
from llama_index.core.indices.property_graph import (
    ImplicitPathExtractor,
    SchemaLLMPathExtractor,
    SimpleLLMPathExtractor,
)
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo, TextNode

from app.airag.knowledge_graph.val_schema import (
    ENTITIES,
    RELATIONS,
    VALIDATION_SCHEMA,
)
from app.core.config import settings


def create_graph_llm(config: dict[str, Any]):
    """
    Create a LLM instance based on the provided configuration.
    Args:
        config (dict): Configuration dictionary containing LLM provider 
            and model information.
    Returns:
        An instance of the specified LLM.
    Raises:
        ValueError: If the LLM provider is unsupported or if required 
        API keys are not configured
    """
    provider = config["llm_provider"]
    model = config["llm_model"]
    if provider == "openai":
        from llama_index.llms.openai import OpenAI

        if not settings.OPENAI_API_KEY:
            raise ValueError("OpenAI API key is not configured")
        return OpenAI(
            model=model,
            temperature=0,
            api_key=settings.OPENAI_API_KEY,
        )
    if provider == "ollama":
        from llama_index.llms.ollama import Ollama

        return Ollama(
            model=model,
            temperature=0,
            base_url=config.get("ollama_base_url", "http://localhost:11434"),
            request_timeout=120,
        )
    raise ValueError(f"Unsupported LLM provider: {provider}")


def create_graph_embedding_model(config: dict[str, Any]):
    """
    Create an embedding model instance based on the provided configuration.
    Args:
        config (dict): Configuration dictionary containing embedding provider
            and model information.
    Returns:
        An instance of the specified embedding model.
    Raises:
        ValueError: If the embedding provider is unsupported or if required
        API keys are not configured.
    """
    provider = config["embedding_provider"]
    model = config["embedding_model"]
    if provider == "openai":
        from llama_index.embeddings.openai import OpenAIEmbedding

        if not settings.OPENAI_API_KEY:
            raise ValueError("OpenAI API key is not configured")
        return OpenAIEmbedding(
            model=model,
            api_key=settings.OPENAI_API_KEY,
        )
    if provider == "ollama":
        from llama_index.embeddings.ollama import OllamaEmbedding

        return OllamaEmbedding(
            model_name=model,
            base_url=config.get("ollama_base_url", "http://localhost:11434"),
        )
    raise ValueError(f"Unsupported embedding provider: {provider}")


def create_kg_extractors(
    config: dict[str, Any],
    *,
    llm,
) -> list:
    """
    Create a list of knowledge graph extractors based on the provided 
    configuration.
    Args:
        config (dict): Configuration dictionary containing extractor 
            names and settings.
        llm: An instance of the LLM to be used by the extractors.
    Returns:
        A list of knowledge graph extractor instances.
    Raises:
        ValueError: If an unsupported extractor name is provided.
    """
    max_paths = int(config.get("max_paths_per_chunk", 10))
    extractors = []
    for name in config.get("extractors", ["schema"]):
        if name == "implicit":
            extractors.append(ImplicitPathExtractor())
        elif name == "simple":
            extractors.append(
                SimpleLLMPathExtractor(
                    llm=llm,
                    max_paths_per_chunk=max_paths,
                )
            )
        elif name == "schema":
            extractors.append(
                SchemaLLMPathExtractor(
                    llm=llm,
                    possible_entities=ENTITIES,
                    possible_relations=RELATIONS,
                    kg_validation_schema=VALIDATION_SCHEMA,
                    strict=bool(config.get("strict_schema", True)),
                    max_triplets_per_chunk=max_paths,
                    allow_additional_properties=False,
                )
            )
        else:
            raise ValueError(f"Unsupported knowledge graph extractor: {name}")
    return extractors


def _node_id(graph_id: int, generation: str, chunk_id: int) -> str:
    """
    Generate a unique node ID for a text node in the knowledge graph.
    Args:
        graph_id (int): The ID of the knowledge graph.
        generation (str): The generation identifier for the graph.
        chunk_id (int): The ID of the document chunk.
    Returns:
        A unique string representing the node ID."""
    return f"kg:{graph_id}:{generation}:chunk:{chunk_id}"


def build_graph_text_nodes(
    chunks: Sequence[Any],
    *,
    graph_id: int,
    generation: str,
    corpus_index_id: int,
) -> list[TextNode]:
    """
    Build a list of TextNode instances from document chunks for the 
    knowledge graph.
    Args:
        chunks (Sequence[Any]): A sequence of document chunks.
        graph_id (int): The ID of the knowledge graph.
        generation (str): The generation identifier for the graph.
        corpus_index_id (int): The ID of the corpus index.
    Returns:
        A list of TextNode instances representing the document chunks in 
        the knowledge graph.
    """
    nodes: list[TextNode] = []
    by_document: dict[int, list[TextNode]] = defaultdict(list)

    for chunk in chunks:
        if chunk.id is None:
            raise ValueError("Document chunk must be persisted before graph indexing")
        metadata = {
            **dict(chunk.chunk_metadata),
            "document_chunk_id": chunk.id,
            "raw_document_id": chunk.raw_document_id,
            "chunking_profile_id": chunk.chunking_profile_id,
            "chunk_index": chunk.chunk_index,
            "corpus_index_id": corpus_index_id,
            "knowledge_graph_index_id": graph_id,
            "graph_generation": generation,
        }
        node = TextNode(
            id_=_node_id(graph_id, generation, chunk.id),
            text=chunk.content,
            metadata=metadata,
        )
        nodes.append(node)
        by_document[chunk.raw_document_id].append(node)

    for document_nodes in by_document.values():
        document_nodes.sort(key=lambda node: int(node.metadata["chunk_index"]))
        for index, node in enumerate(document_nodes):
            if index > 0:
                previous = document_nodes[index - 1]
                node.relationships[NodeRelationship.PREVIOUS] = RelatedNodeInfo(
                    node_id=previous.id_
                )
            if index + 1 < len(document_nodes):
                following = document_nodes[index + 1]
                node.relationships[NodeRelationship.NEXT] = RelatedNodeInfo(
                    node_id=following.id_
                )
    return nodes


def build_property_graph_index(
    *,
    nodes: list[TextNode],
    graph_store,
    llm,
    embedding_model,
    kg_extractors: list,
) -> PropertyGraphIndex:
    """
    Build a PropertyGraphIndex instance for the knowledge graph.
    Args:
        nodes (list[TextNode]): A list of TextNode instances representing
            the document chunks in the knowledge graph.
        graph_store: The property graph store to be used for indexing.
        llm: An instance of the LLM to be used for knowledge graph extraction.
        embedding_model: An instance of the embedding model to be used for
            generating embeddings for the nodes.
        kg_extractors (list): A list of knowledge graph extractor instances.
    Returns:
        A PropertyGraphIndex instance representing the knowledge graph.
    """
    return PropertyGraphIndex(
        nodes=nodes,
        property_graph_store=graph_store,
        llm=llm,
        embed_model=embedding_model,
        kg_extractors=kg_extractors,
    )
