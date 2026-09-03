from pathlib import Path

import pytest

from app.core.config import Settings


EXPECTED_OPENAI_CHAT_MODELS = (
    "gpt-4o-mini",
    "gpt-4.1-mini",
    "gpt-4.1",
    "o3",
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.2",
    "gpt-5.1",
    "gpt-5",
    "gpt-5-mini",
)


def test_unit_test_environment_provides_required_settings_without_env_file():
    settings = Settings(_env_file=Path("missing-test-env-file"))

    assert settings.ASYNC_DATABASE_URL
    assert settings.ADMIN_USERNAME
    assert settings.ADMIN_EMAIL
    assert settings.ADMIN_PASSWORD
    assert settings.NEO4J_URI
    assert settings.NEO4J_USERNAME
    assert settings.NEO4J_PASSWORD
    assert settings.SECRET_KEY
    assert settings.ALGORITHM
    assert settings.OPENAI_API_KEY


def test_settings_exposes_locked_policy_and_ignores_environment(monkeypatch):
    monkeypatch.setenv("ALGORITHM", "HS512")
    monkeypatch.setenv("OPENAI_CHAT_MODELS", '["deployment-model"]')
    monkeypatch.setenv("OPEN_AI_DEFAULT_MODEL", "deployment-model")
    monkeypatch.setenv("OLLAMA_DEFAULT_MODEL", "deployment-model")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1")
    monkeypatch.setenv("FIXED_ROLES", '["deployment-role"]')
    monkeypatch.setenv("MAX_UPLOAD_SIZE", "1")

    configured = Settings(_env_file=Path("missing-test-env-file"))

    assert configured.ALGORITHM == "HS256"
    assert configured.OPENAI_CHAT_MODELS == EXPECTED_OPENAI_CHAT_MODELS
    assert configured.OPEN_AI_DEFAULT_MODEL == "gpt-4o-mini"
    assert configured.OLLAMA_DEFAULT_MODEL == "qwen2.5:1.5b-instruct"
    assert configured.ACCESS_TOKEN_EXPIRE_MINUTES == 360
    assert configured.FIXED_ROLES == ("admin", "student", "teacher")
    assert configured.MAX_UPLOAD_SIZE == 248 * 1024 * 1024
    assert {
        "ALGORITHM",
        "OPENAI_CHAT_MODELS",
        "OPEN_AI_DEFAULT_MODEL",
        "OLLAMA_DEFAULT_MODEL",
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "FIXED_ROLES",
        "MAX_UPLOAD_SIZE",
    }.isdisjoint(Settings.model_fields)


def test_application_policy_invariants():
    from app.core import policies

    assert policies.OPENAI_CHAT_MODELS == EXPECTED_OPENAI_CHAT_MODELS
    assert policies.OPENAI_CHAT_MODELS
    assert all(model.strip() for model in policies.OPENAI_CHAT_MODELS)
    assert len(policies.OPENAI_CHAT_MODELS) == len(set(policies.OPENAI_CHAT_MODELS))
    assert policies.OPEN_AI_DEFAULT_MODEL in policies.OPENAI_CHAT_MODELS
    assert policies.FIXED_ROLES == ("admin", "student", "teacher")
    assert len(policies.FIXED_ROLES) == len(set(policies.FIXED_ROLES))
    assert all(role.strip() for role in policies.FIXED_ROLES)
    assert policies.ALGORITHM == "HS256"
    assert policies.ACCESS_TOKEN_EXPIRE_MINUTES > 0
    assert policies.MAX_UPLOAD_SIZE > 0


@pytest.mark.parametrize(
    ("attribute", "policy_name"),
    [
        ("ALGORITHM", "ALGORITHM"),
        ("OPENAI_CHAT_MODELS", "OPENAI_CHAT_MODELS"),
        ("OPEN_AI_DEFAULT_MODEL", "OPEN_AI_DEFAULT_MODEL"),
        ("OLLAMA_DEFAULT_MODEL", "OLLAMA_DEFAULT_MODEL"),
        ("ACCESS_TOKEN_EXPIRE_MINUTES", "ACCESS_TOKEN_EXPIRE_MINUTES"),
        ("FIXED_ROLES", "FIXED_ROLES"),
        ("MAX_UPLOAD_SIZE", "MAX_UPLOAD_SIZE"),
    ],
)
def test_settings_policy_attributes_match_policy_source(attribute, policy_name):
    from app.core import policies

    configured = Settings(_env_file=Path("missing-test-env-file"))

    assert getattr(configured, attribute) == getattr(policies, policy_name)
