from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama


# local imports
from app.core.config import settings
OPENAI_API_KEY = settings.OPENAI_API_KEY

def get_openai_llm(model_name: str = "gpt-4o-mini",
            temperature: float = 0.0,) -> ChatOpenAI | None:
    
    """
    Wrapper function to initialize and return an OpenAI LLM instance.
    Args:
        model_name: The name of the OpenAI model to use (default: "gpt-4o-mini").
        temperature: The temperature setting for the LLM (default: 0.0).
    Returns:
        An instance of ChatOpenAI initialized with the specified model and 
        temperature, or None if initialization fails.
    """
    try:
        open_ai_llm = ChatOpenAI(model=model_name, temperature=temperature)
        return open_ai_llm
    except Exception as e:
        print(f"Error initializing OpenAI LLM: {e}")
        return None     
    
def get_ollama_llm(
    model_name: str = "llama3.1",
    temperature: float = 0.0,
    base_url: str = "http://localhost:11434",
) -> ChatOllama | None:
    try:
        ollama_llm = ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=base_url,
        )
        return ollama_llm
    except Exception as e:
        print(f"Error initializing Ollama LLM: {e}")
        return None
    
def get_llm(model_name: str = "gpt-4o-mini",
            temperature: float = 0.0,
            provider: str = "openai") -> ChatOpenAI | ChatOllama | None:
    """
    Factory function to get an LLM instance based on the specified provider.
    Args:
        model_name: The name of the model to use (default: "gpt-4o-mini").
        temperature: The temperature setting for the LLM (default: 0.0).
        provider: The LLM provider to use ("openai" or "ollama", default: "openai").
    Returns:
        An instance of the specified LLM, or None if initialization fails or 
        if an unsupported provider is specified.
    """
    if provider == "openai":
        return get_openai_llm(model_name=model_name, temperature=temperature)
    elif provider == "ollama":
        return get_ollama_llm(model_name=model_name, temperature=temperature)
    else:
        print(f"Unsupported LLM provider: {provider}")
        return None         