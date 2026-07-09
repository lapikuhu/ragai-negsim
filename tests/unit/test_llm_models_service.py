import pytest
from types import SimpleNamespace

from app.airag.llm_models import llm_models
from app.services import llm_models_service


@pytest.fixture(autouse=True)
def clear_catalog_cache():
    llm_models_service.clear_llm_model_catalog_cache()
    yield
    llm_models_service.clear_llm_model_catalog_cache()


def test_ollama_helpers_use_client_host_and_list_response(monkeypatch):
    captured = []

    class FakeOllamaClient:
        def __init__(self, **kwargs):
            captured.append(kwargs)

        def list(self):
            return SimpleNamespace(
                models=[
                    SimpleNamespace(model="qwen2.5:3b", size=2 * 1024**3),
                    SimpleNamespace(model="llama3.2:1b", size=1024**3),
                ]
            )

    monkeypatch.setattr(llm_models, "OllamaClient", FakeOllamaClient)

    assert llm_models.get_available_ollama_models("http://localhost:11434") == [
        "qwen2.5:3b",
        "llama3.2:1b",
    ]
    assert llm_models.get_ollama_model_sizes("http://localhost:11434") == {
        "qwen2.5:3b": 2.0,
        "llama3.2:1b": 1.0,
    }
    assert captured == [
        {"host": "http://localhost:11434"},
        {"host": "http://localhost:11434"},
    ]


def test_catalog_returns_openai_ollama_sizes_and_gpu_memory(monkeypatch):
    monkeypatch.setattr(llm_models_service.settings, "OPENAI_CHAT_MODELS", ["gpt-4o-mini", "gpt-4o"])
    monkeypatch.setattr(llm_models_service, "get_available_ollama_models", lambda: ["qwen2.5:3b", "llama3.2:1b"])
    monkeypatch.setattr(
        llm_models_service,
        "get_ollama_model_sizes",
        lambda: {"qwen2.5:3b": 2.2, "llama3.2:1b": 1.3},
    )
    monkeypatch.setattr(llm_models_service, "get_gpu_memory_gib", lambda: 8.0)

    catalog = llm_models_service.list_llm_model_catalog()

    assert catalog.gpu_memory_gib == 8.0
    openai = next(provider for provider in catalog.providers if provider.provider == "openai")
    ollama = next(provider for provider in catalog.providers if provider.provider == "ollama")
    assert [model.name for model in openai.models] == ["gpt-4o-mini", "gpt-4o"]
    assert [(model.name, model.size_gib) for model in ollama.models] == [
        ("qwen2.5:3b", 2.2),
        ("llama3.2:1b", 1.3),
    ]


def test_catalog_degrades_when_ollama_lookup_fails(monkeypatch):
    monkeypatch.setattr(llm_models_service.settings, "OPENAI_CHAT_MODELS", ["gpt-4o-mini"])
    monkeypatch.setattr(
        llm_models_service,
        "get_available_ollama_models",
        lambda: (_ for _ in ()).throw(ValueError("ollama unavailable")),
    )
    monkeypatch.setattr(llm_models_service, "get_gpu_memory_gib", lambda: None)

    catalog = llm_models_service.list_llm_model_catalog()

    ollama = next(provider for provider in catalog.providers if provider.provider == "ollama")
    assert ollama.models == []
    assert ollama.error == "ollama unavailable"


def test_normalize_llm_selection_validates_against_catalog(monkeypatch):
    monkeypatch.setattr(llm_models_service.settings, "OPENAI_CHAT_MODELS", ["gpt-4o-mini"])
    monkeypatch.setattr(llm_models_service, "get_available_ollama_models", lambda: ["qwen2.5:3b"])
    monkeypatch.setattr(llm_models_service, "get_ollama_model_sizes", lambda: {"qwen2.5:3b": 2.2})
    monkeypatch.setattr(llm_models_service, "get_gpu_memory_gib", lambda: None)

    assert llm_models_service.normalize_llm_selection(None, None) == {
        "provider": "openai",
        "model": "gpt-4o-mini",
    }
    assert llm_models_service.normalize_llm_selection("ollama", "qwen2.5:3b") == {
        "provider": "ollama",
        "model": "qwen2.5:3b",
    }
    with pytest.raises(ValueError, match="Unsupported openai LLM model"):
        llm_models_service.normalize_llm_selection("openai", "unknown")


def test_normalize_rag_llm_components_defaults_and_rejects_unknown(monkeypatch):
    monkeypatch.setattr(llm_models_service.settings, "OPENAI_CHAT_MODELS", ["gpt-4o-mini"])
    monkeypatch.setattr(llm_models_service, "get_available_ollama_models", lambda: ["qwen2.5:3b"])
    monkeypatch.setattr(llm_models_service, "get_ollama_model_sizes", lambda: {"qwen2.5:3b": 2.2})
    monkeypatch.setattr(llm_models_service, "get_gpu_memory_gib", lambda: None)

    normalized = llm_models_service.normalize_rag_llm_components(
        {"generate": {"provider": "ollama", "model": "qwen2.5:3b"}}
    )

    assert normalized["generate"] == {"provider": "ollama", "model": "qwen2.5:3b"}
    assert normalized["rewrite"] == {"provider": "openai", "model": "gpt-4o-mini"}
    with pytest.raises(ValueError, match="Unknown LLM components"):
        llm_models_service.normalize_rag_llm_components({"unknown": {}})
