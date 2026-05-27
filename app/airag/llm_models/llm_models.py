from langchain_openai import ChatOpenAI

# local imports
from core.config import settings
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