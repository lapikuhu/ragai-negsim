from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.runnables.config import RunnableConfig
from ollama import Client as OllamaClient
from openai import OpenAI
import pyopencl as cl
from functools import lru_cache

# local imports
from app.core.config import settings
from app.airag.observability.llm_usage import bind_runnable_config
OPENAI_API_KEY = settings.OPENAI_API_KEY
OLLAMA_BASE_URL = settings.OLLAMA_BASE_URL

@lru_cache
def get_gpu_memory_gib() -> float | None:
    """
    Returns the amount of GPU memory available in GiB.
    If no GPU is found, returns None.
    Args: 
        None
    Returns:
        The amount of GPU memory in GiB, or None if no GPU is found."""
    memories = [
        device.global_mem_size
        for platform in cl.get_platforms()
        for device in platform.get_devices(
            device_type=cl.device_type.GPU
        )
    ]

    if not memories:
        return None

    # Use the largest GPU, avoiding laptop integrated-GPU confusion.
    return round(max(memories) / 1024**3, 1)

def _require_openai_api_key() -> str:
    """
    Return the configured OpenAI API key or raise a clear error.
    Raises:
        ValueError: If the OpenAI API key is not configured.
    Returns:
        The OpenAI API key as a string."""
    if not OPENAI_API_KEY:
        raise ValueError(
            "OpenAI API key is not configured. Set OPENAI_API_KEY before using OpenAI-backed simulation turns."
        )
    return OPENAI_API_KEY

def get_openai_llm(model_name: str = "gpt-4o-mini",
            temperature: float = 0.0,
            config: RunnableConfig | None = None,
            tags: list[str] | None = None,
            metadata: dict[str, object] | None = None,
            run_name: str | None = None,) -> ChatOpenAI:
    """
    Wrapper function to initialize and return an OpenAI LLM instance.
    Args:
        model_name: The name of the OpenAI model to use 
            (default: "gpt-4o-mini").
        temperature: The temperature setting for the LLM (default: 0.0).
    Returns:
        An instance of ChatOpenAI initialized with the specified model and 
        temperature.
    Raises:
        ValueError: If the OpenAI API key is missing or initialization fails.
    """
    try:
        open_ai_llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=_require_openai_api_key(),
        )
        return bind_runnable_config(
            open_ai_llm,
            config,
            tags=["provider:openai", f"model:{model_name}", *(tags or [])],
            metadata={
                "provider": "openai",
                "model_name": model_name,
                **(metadata or {}),
            },
            run_name=run_name,
        )
    except Exception as e:
        raise ValueError(f"Error initializing OpenAI LLM: {e}") from e
    
def get_ollama_llm(
    model_name: str = "qwen2.5:3b-instruct",
    temperature: float = 0.0,
    base_url: str = OLLAMA_BASE_URL,
    config: RunnableConfig | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, object] | None = None,
    run_name: str | None = None,
) -> ChatOllama | None:
    """
    Wrapper function to initialize and return an Ollama LLM instance.
    Args:
        model_name: The name of the Ollama model to use (default: 
            "qwen2.5:3b-instruct").
        temperature: The temperature setting for the LLM (default: 0.0).
        base_url: The base URL for the Ollama API 
            (default: OLLAMA_BASE_URL).
    Returns:
        An instance of ChatOllama initialized with the specified model, 
        temperature, and base URL.
    """
    try:
        ollama_llm = ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=base_url,
        )
        return bind_runnable_config(
            ollama_llm,
            config,
            tags=["provider:ollama", f"model:{model_name}", *(tags or [])],
            metadata={
                "provider": "ollama",
                "model_name": model_name,
                **(metadata or {}),
            },
            run_name=run_name,
        )
    except Exception as e:
        print(f"Error initializing Ollama LLM: {e}")
        return None
    
def get_llm(model_name: str = "gpt-4o-mini",
            temperature: float = 0.0,
            provider: str = "openai",
            config: RunnableConfig | None = None,
            tags: list[str] | None = None,
            metadata: dict[str, object] | None = None,
            run_name: str | None = None) -> ChatOpenAI | ChatOllama | None:
    """
    Factory function to get an LLM instance based on the specified provider.
    Args:
        model_name: The name of the model to use (default: "gpt-4o-mini").
        temperature: The temperature setting for the LLM (default: 0.0).
        provider: The LLM provider to use ("openai" or "ollama", default: "openai").
    Returns:
        An instance of the specified LLM.
    Raises:
        ValueError: If initialization fails or the provider is unsupported.
    """
    if provider == "openai":
        return get_openai_llm(
            model_name=model_name,
            temperature=temperature,
            config=config,
            tags=tags,
            metadata=metadata,
            run_name=run_name,
        )
    elif provider == "ollama":
        return get_ollama_llm(
            model_name=model_name,
            temperature=temperature,
            config=config,
            tags=tags,
            metadata=metadata,
            run_name=run_name,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    
# TODO: Move ollama base URL to config file
def _ollama_model_name(model) -> str:
    name = getattr(model, "model", None) or getattr(model, "name", None)
    if name is None and isinstance(model, dict):
        name = model.get("model") or model.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Ollama model entry is missing a model name")
    return name


def _ollama_model_size(model) -> int | float | None:
    size = getattr(model, "size", None)
    if size is None and isinstance(model, dict):
        size = model.get("size")
    return size


def get_available_ollama_models(base_url: str = OLLAMA_BASE_URL) -> list[str]:
    """
    Fetches the list of available Ollama models from the specified base URL.
    Args:
        base_url: The base URL for the Ollama API 
            (default: OLLAMA_BASE_URL).
    Returns:
        A list of available Ollama model names.
    Raises:
        ValueError: If fetching the models fails.
    """
    try:
        client = OllamaClient(host=base_url)
        response = client.list()
        models = response.models if hasattr(response, "models") else response
        return [_ollama_model_name(model) for model in models]
    except Exception as e:
        raise ValueError(f"Error fetching available Ollama models: {e}") from e


def get_ollama_model_sizes(base_url: str = OLLAMA_BASE_URL) -> dict[str, str]:
    """
    Fetches the sizes of available Ollama models from the specified base URL.
    Args:
        base_url: The base URL for the Ollama API (default: OLLAMA_BASE_URL).
    Returns:
        A dictionary mapping model names to their sizes.
    Raises:
        ValueError: If fetching the model sizes fails.
    """
    try:
        client = OllamaClient(host=base_url)
        response = client.list()
        models = response.models if hasattr(response, "models") else response
        return {
            _ollama_model_name(model): _ollama_model_size(model) / (1024**3)
            for model in models
            if _ollama_model_size(model) is not None
        } # Convert size from bytes to GB
    except Exception as e:
        raise ValueError(f"Error fetching available Ollama model sizes: {e}") from e

@lru_cache
def get_openai_models() -> list[str]:
    """
    Fetches the list of available OpenAI models.
    Returns:
        A list of available OpenAI model names.
    Raises:
        ValueError: If fetching the models fails.
    """
    try:
        openai_client = OpenAI(api_key=_require_openai_api_key())
        models = openai_client.models.list()
        return [model.id for model in models.data]
    except Exception as e:
        raise ValueError(f"Error fetching available OpenAI models: {e}") from e