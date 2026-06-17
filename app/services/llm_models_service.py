from functools import lru_cache
from time import monotonic

from app.airag.llm_models.llm_models import (
    get_available_ollama_models,
    get_gpu_memory_gib,
    get_ollama_model_sizes,
)
from app.core.config import settings
from app.schemas.llm_models_schemas import (
    LLMModelCatalogItem,
    LLMModelCatalogResponse,
    LLMProvider,
    LLMProviderCatalog,
)

DEFAULT_OPENAI_CHAT_MODEL = "gpt-4o-mini"
CATALOG_CACHE_TTL_SECONDS = 30
# Sketchy.... should have a way to read them.
RAG_LLM_COMPONENTS = (
    "document_grader",
    "rewrite",
    "generate",
    "hallucination_grader",
    "answer_grader",
    "fallback",
)

def get_default_openai_chat_model() -> str:
    """
    Return the default OpenAI chat model from settings or a predefined default.
    Returns:
        str: The default OpenAI chat model name.
    """
    models = [model for model in settings.OPENAI_CHAT_MODELS if model.strip()]
    return models[0] if models else DEFAULT_OPENAI_CHAT_MODEL


def list_llm_model_catalog() -> LLMModelCatalogResponse:
    """
    List the available LLM models from all supported providers.
    Returns:
        LLMModelCatalogResponse: A response containing the available LLM 
        models and their details.
    """
    return _list_llm_model_catalog_cached(_catalog_cache_bucket())


def clear_llm_model_catalog_cache() -> None:
    _list_llm_model_catalog_cached.cache_clear()


def _catalog_cache_bucket() -> int:
    return int(monotonic() // CATALOG_CACHE_TTL_SECONDS)


@lru_cache(maxsize=2)
def _list_llm_model_catalog_cached(_cache_bucket: int) -> LLMModelCatalogResponse:
    openai_models = [
        LLMModelCatalogItem(name=model)
        for model in settings.OPENAI_CHAT_MODELS
        if model.strip()
    ]
    if not openai_models:
        openai_models = [LLMModelCatalogItem(name=DEFAULT_OPENAI_CHAT_MODEL)]

    providers = [
        LLMProviderCatalog(provider="openai", models=openai_models),
    ]

    try:
        ollama_model_names = get_available_ollama_models()
        ollama_model_sizes = get_ollama_model_sizes()
        providers.append(
            LLMProviderCatalog(
                provider="ollama",
                models=[
                    LLMModelCatalogItem(
                        name=model_name,
                        size_gib=round(float(ollama_model_sizes[model_name]), 1)
                        if model_name in ollama_model_sizes
                        else None,
                    )
                    for model_name in ollama_model_names
                ],
            )
        )
    except ValueError as exc:
        providers.append(
            LLMProviderCatalog(
                provider="ollama",
                models=[],
                error=str(exc),
            )
        )

    return LLMModelCatalogResponse(
        providers=providers,
        gpu_memory_gib=_safe_gpu_memory_gib(),
    )


def validate_llm_model_selection(provider: LLMProvider, model: str) -> None:
    """
    Validate that the selected LLM model is available in the catalog for 
    the specified provider.
    Args:
        provider (LLMProvider): The LLM provider.
        model (str): The LLM model name.
    """
    catalog = list_llm_model_catalog()
    for provider_catalog in catalog.providers:
        if provider_catalog.provider != provider:
            continue
        if any(item.name == model for item in provider_catalog.models):
            return
        raise ValueError(f"Unsupported {provider} LLM model: {model}")
    raise ValueError(f"Unsupported LLM provider: {provider}")


def _safe_gpu_memory_gib() -> float | None:
    try:
        return get_gpu_memory_gib()
    except Exception:
        return None


def default_llm_selection() -> dict[str, str]:
    """
    Return the default LLM selection.
    Returns:
        dict[str, str]: A dictionary containing the default LLM provider 
        and model.
    """
    return {"provider": "openai", "model": get_default_openai_chat_model()}


def normalize_llm_selection(provider: str | None, model: str | None) -> dict[str, str]:
    """
    Normalize and validate the LLM selection based on the provided provider 
    and model.
    Args:
        provider (str | None): The LLM provider to use ("openai" or "ollama").
        model (str | None): The LLM model name.
    Returns:
        dict[str, str]: A dictionary containing the normalized LLM provider
            and model.
    Raises:
        ValueError: If the provider or model is unsupported or invalid.
    """
    normalized_provider = (provider or "openai").strip().lower()
    if normalized_provider not in {"openai", "ollama"}:
        raise ValueError(f"Unsupported LLM provider: {normalized_provider}")

    normalized_model = (model or "").strip()
    if not normalized_model:
        if normalized_provider == "openai":
            normalized_model = get_default_openai_chat_model()
        else:
            raise ValueError("Ollama LLM model is required")

    validate_llm_model_selection(normalized_provider, normalized_model)
    return {"provider": normalized_provider, "model": normalized_model}


def normalize_rag_llm_components(value: object | None) -> dict[str, dict[str, str]]:
    """
    Normalize and validate the RAG LLM components selection.
    Args:
        value (object | None): The RAG LLM components selection.
    Returns:
        dict[str, dict[str, str]]: A dictionary mapping component names to 
            their respective provider and model selections.
    Raises:
        ValueError: If the selection is invalid or contains unknown components.
    """
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("llm_components must be a dictionary")

    unknown = sorted(set(value) - set(RAG_LLM_COMPONENTS))
    if unknown:
        raise ValueError(f"Unknown LLM components: {', '.join(unknown)}")

    normalized: dict[str, dict[str, str]] = {}
    for component in RAG_LLM_COMPONENTS:
        raw_selection = value.get(component, {})
        if not isinstance(raw_selection, dict):
            raise ValueError(f"{component} LLM selection must be a dictionary")
        normalized[component] = normalize_llm_selection(
            raw_selection.get("provider"),
            raw_selection.get("model"),
        )
    return normalized
