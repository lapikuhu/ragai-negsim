from pathlib import Path

import pytest
import yaml
from dotenv import dotenv_values


LOCKED_POLICY_NAMES = {
    "ALGORITHM",
    "OPENAI_CHAT_MODELS",
    "OPEN_AI_DEFAULT_MODEL",
    "OLLAMA_DEFAULT_MODEL",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "FIXED_ROLES",
    "MAX_UPLOAD_SIZE",
}


@pytest.mark.parametrize("compose_file", ["compose.yaml", "compose.coolify.yaml"])
def test_compose_backend_does_not_forward_locked_policy(compose_file):
    document = yaml.safe_load(Path(compose_file).read_text(encoding="utf-8"))
    environment = document["services"]["backend"]["environment"]

    assert LOCKED_POLICY_NAMES.isdisjoint(environment)


def test_env_example_does_not_advertise_locked_policy():
    example = dotenv_values(".env.example")

    assert LOCKED_POLICY_NAMES.isdisjoint(example)
    assert "SECRET_KEY" in example
    assert "LANGSMITH_TRACING" in example
