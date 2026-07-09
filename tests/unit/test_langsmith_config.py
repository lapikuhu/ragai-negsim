import os
import warnings
from types import SimpleNamespace

from app.core.config import configure_langsmith_environment


def _settings(**overrides):
    defaults = {
        "LANGSMITH_API_KEY": None,
        "LANGSMITH_TRACING": False,
        "LANGSMITH_PROJECT": None,
        "LANGSMITH_ENDPOINT": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_configure_langsmith_environment_enables_tracing_v2(monkeypatch):
    configure_langsmith_environment(
        _settings(
            LANGSMITH_API_KEY="test-key",
            LANGSMITH_TRACING=True,
            LANGSMITH_PROJECT="test-project",
            LANGSMITH_ENDPOINT="https://example.test",
        )
    )

    assert os.environ["LANGSMITH_API_KEY"] == "test-key"
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "test-project"
    assert os.environ["LANGSMITH_ENDPOINT"] == "https://example.test"


def test_configure_langsmith_environment_pydantic_values_override_env(monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "existing-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGSMITH_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_PROJECT", "existing-project")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://existing.test")

    configure_langsmith_environment(
        _settings(
            LANGSMITH_API_KEY="settings-key",
            LANGSMITH_TRACING=True,
            LANGSMITH_PROJECT="settings-project",
            LANGSMITH_ENDPOINT="https://settings.test",
        )
    )

    assert os.environ["LANGSMITH_API_KEY"] == "settings-key"
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "settings-project"
    assert os.environ["LANGSMITH_ENDPOINT"] == "https://settings.test"


def test_configure_langsmith_environment_warns_when_tracing_enabled_without_key(monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        configure_langsmith_environment(_settings(LANGSMITH_TRACING=True))

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_TRACING_V2"] == "true"
    assert any(
        "LANGSMITH_API_KEY is missing" in str(warning.message)
        for warning in caught
    )


def test_configure_langsmith_environment_disables_tracing_and_removes_empty_values(monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "existing-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_PROJECT", "existing-project")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://existing.test")

    configure_langsmith_environment(_settings())

    assert "LANGSMITH_API_KEY" not in os.environ
    assert os.environ["LANGSMITH_TRACING"] == "false"
    assert os.environ["LANGSMITH_TRACING_V2"] == "false"
    assert "LANGSMITH_PROJECT" not in os.environ
    assert "LANGSMITH_ENDPOINT" not in os.environ
