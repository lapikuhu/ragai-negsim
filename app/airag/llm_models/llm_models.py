from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.runnables.config import RunnableConfig


# local imports
from app.core.config import settings
from app.airag.observability.llm_usage import bind_runnable_config
OPENAI_API_KEY = settings.OPENAI_API_KEY


def _require_openai_api_key() -> str:
    """Return the configured OpenAI API key or raise a clear error."""
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
        model_name: The name of the OpenAI model to use (default: "gpt-4o-mini").
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
    model_name: str = "llama3.1",
    temperature: float = 0.0,
    base_url: str = "http://localhost:11434",
    config: RunnableConfig | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, object] | None = None,
    run_name: str | None = None,
) -> ChatOllama | None:
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
