from pathlib import Path

from app.core.config import Settings


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
