from unittest.mock import Mock

import pytest

from app.airag.llm_models import llm_models


def test_openai_llm_binds_runnable_config_by_default(monkeypatch):
    raw_model = object()
    bound_model = object()
    constructor = Mock(return_value=raw_model)
    binder = Mock(return_value=bound_model)
    monkeypatch.setattr(llm_models, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_models, "ChatOpenAI", constructor)
    monkeypatch.setattr(llm_models, "bind_runnable_config", binder)

    result = llm_models.get_openai_llm(model_name="judge-model")

    assert result is bound_model
    binder.assert_called_once()
    assert binder.call_args.args[0] is raw_model


def test_openai_llm_returns_raw_model_when_binding_is_disabled(monkeypatch):
    raw_model = object()
    binder = Mock()
    monkeypatch.setattr(llm_models, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_models, "ChatOpenAI", Mock(return_value=raw_model))
    monkeypatch.setattr(llm_models, "bind_runnable_config", binder)

    result = llm_models.get_openai_llm(
        model_name="judge-model",
        do_not_bind_runnable_config=True,
    )

    assert result is raw_model
    binder.assert_not_called()


def test_ollama_llm_binds_runnable_config_by_default(monkeypatch):
    raw_model = object()
    bound_model = object()
    binder = Mock(return_value=bound_model)
    monkeypatch.setattr(llm_models, "ChatOllama", Mock(return_value=raw_model))
    monkeypatch.setattr(llm_models, "bind_runnable_config", binder)

    result = llm_models.get_ollama_llm(model_name="judge-model")

    assert result is bound_model
    binder.assert_called_once()
    assert binder.call_args.args[0] is raw_model


def test_ollama_llm_returns_raw_model_when_binding_is_disabled(monkeypatch):
    raw_model = object()
    binder = Mock()
    monkeypatch.setattr(llm_models, "ChatOllama", Mock(return_value=raw_model))
    monkeypatch.setattr(llm_models, "bind_runnable_config", binder)

    result = llm_models.get_ollama_llm(
        model_name="judge-model",
        do_not_bind_runnable_config=True,
    )

    assert result is raw_model
    binder.assert_not_called()


@pytest.mark.parametrize(
    ("provider", "factory_name"),
    (("openai", "get_openai_llm"), ("ollama", "get_ollama_llm")),
)
def test_get_llm_forwards_raw_model_option(monkeypatch, provider, factory_name):
    provider_model = object()
    factory = Mock(return_value=provider_model)
    monkeypatch.setattr(llm_models, factory_name, factory)

    result = llm_models.get_llm(
        provider=provider,
        model_name="judge-model",
        do_not_bind_runnable_config=True,
    )

    assert result is provider_model
    assert factory.call_args.kwargs["do_not_bind_runnable_config"] is True


def test_get_llm_still_rejects_unsupported_provider():
    with pytest.raises(ValueError, match="Unsupported LLM provider: invalid"):
        llm_models.get_llm(provider="invalid")
