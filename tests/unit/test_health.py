import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.dependencies import get_session, get_settings
from app.web.routes import health


@pytest.fixture
def health_client(monkeypatch: pytest.MonkeyPatch):
    app = FastAPI()
    app.include_router(health.router)

    session = object()
    settings = SimpleNamespace(
        NEO4J_URI="neo4j://neo4j.example.test:7687",
        NEO4J_DATABASE="neo4j",
        NEO4J_USERNAME="neo4j",
        NEO4J_PASSWORD="secret-password",
    )

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as client:
        yield client, session, settings


def _set_check_results(
    monkeypatch: pytest.MonkeyPatch,
    *,
    postgres_error: Exception | None = None,
    neo4j_error: Exception | None = None,
) -> None:
    async def postgres_check(_session):
        if postgres_error is not None:
            raise postgres_error

    async def neo4j_check(_settings):
        if neo4j_error is not None:
            raise neo4j_error

    monkeypatch.setattr(health, "check_postgres", postgres_check, raising=False)
    monkeypatch.setattr(health, "check_neo4j", neo4j_check, raising=False)


def test_liveness_does_not_require_dependency_checks(
    health_client,
    monkeypatch: pytest.MonkeyPatch,
):
    async def unavailable(_dependency):
        raise RuntimeError("dependency unavailable")

    monkeypatch.setattr(health, "check_postgres", unavailable, raising=False)
    monkeypatch.setattr(health, "check_neo4j", unavailable, raising=False)

    client, _, _ = health_client
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_returns_ready_when_both_dependencies_respond(
    health_client,
    monkeypatch: pytest.MonkeyPatch,
):
    _set_check_results(monkeypatch)
    client, _, _ = health_client

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"postgres": "ok", "neo4j": "ok"},
    }


@pytest.mark.parametrize(
    ("postgres_error", "neo4j_error", "expected_checks", "expected_message"),
    [
        (
            RuntimeError("postgresql://admin:secret@db.example.test/app"),
            None,
            {"postgres": "unavailable", "neo4j": "ok"},
            "PostgreSQL connection check failed",
        ),
        (
            None,
            RuntimeError("neo4j://neo4j:secret@graph.example.test"),
            {"postgres": "ok", "neo4j": "unavailable"},
            "Neo4j connection check failed",
        ),
        (
            RuntimeError("postgres secret"),
            RuntimeError("neo4j secret"),
            {"postgres": "unavailable", "neo4j": "unavailable"},
            "PostgreSQL and Neo4j connection checks failed",
        ),
    ],
)
def test_readiness_returns_sanitized_503_for_dependency_failures(
    health_client,
    monkeypatch: pytest.MonkeyPatch,
    postgres_error,
    neo4j_error,
    expected_checks,
    expected_message,
):
    _set_check_results(
        monkeypatch,
        postgres_error=postgres_error,
        neo4j_error=neo4j_error,
    )
    client, _, _ = health_client

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": expected_checks,
        "message": expected_message,
    }
    assert "secret" not in response.text
    assert "example.test" not in response.text


@pytest.mark.parametrize(
    ("stalled_dependency", "expected_checks", "expected_message"),
    [
        (
            "postgres",
            {"postgres": "unavailable", "neo4j": "ok"},
            "PostgreSQL connection check failed",
        ),
        (
            "neo4j",
            {"postgres": "ok", "neo4j": "unavailable"},
            "Neo4j connection check failed",
        ),
    ],
)
def test_readiness_times_out_a_stalled_dependency(
    health_client,
    monkeypatch: pytest.MonkeyPatch,
    stalled_dependency,
    expected_checks,
    expected_message,
):
    async def postgres_check(_session):
        if stalled_dependency == "postgres":
            await asyncio.sleep(1)

    async def neo4j_check(_settings):
        if stalled_dependency == "neo4j":
            await asyncio.sleep(1)

    monkeypatch.setattr(health, "check_postgres", postgres_check, raising=False)
    monkeypatch.setattr(health, "check_neo4j", neo4j_check, raising=False)
    monkeypatch.setattr(
        health,
        "READINESS_TIMEOUT_SECONDS",
        0.001,
        raising=False,
    )
    client, _, _ = health_client

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": expected_checks,
        "message": expected_message,
    }


@pytest.mark.asyncio
async def test_postgres_check_executes_select_one():
    statements = []

    class RecordingSession:
        async def exec(self, statement):
            statements.append(str(statement))

    check_postgres = getattr(health, "check_postgres", None)
    assert callable(check_postgres), "PostgreSQL readiness check is missing"

    await check_postgres(RecordingSession())

    assert statements == ["SELECT 1"]


@pytest.mark.asyncio
async def test_neo4j_check_executes_return_one_and_closes_driver(
    monkeypatch: pytest.MonkeyPatch,
):
    calls = []

    class RecordingDriver:
        async def execute_query(self, query, **kwargs):
            calls.append((query, kwargs))

        async def close(self):
            calls.append(("close", {}))

    driver = RecordingDriver()
    graph_database = SimpleNamespace(
        driver=lambda uri, auth: calls.append(("driver", {"uri": uri, "auth": auth})) or driver
    )
    monkeypatch.setattr(
        health,
        "AsyncGraphDatabase",
        graph_database,
        raising=False,
    )
    settings = SimpleNamespace(
        NEO4J_URI="neo4j://graph.example.test:7687",
        NEO4J_DATABASE="analytics",
        NEO4J_USERNAME="reader",
        NEO4J_PASSWORD="password",
    )
    check_neo4j = getattr(health, "check_neo4j", None)
    assert callable(check_neo4j), "Neo4j readiness check is missing"

    await check_neo4j(settings)

    assert calls == [
        (
            "driver",
            {
                "uri": "neo4j://graph.example.test:7687",
                "auth": ("reader", "password"),
            },
        ),
        ("RETURN 1", {"database_": "analytics"}),
        ("close", {}),
    ]


@pytest.mark.asyncio
async def test_neo4j_check_closes_driver_when_query_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    closed = False

    class FailingDriver:
        async def execute_query(self, _query, **_kwargs):
            raise RuntimeError("query failed")

        async def close(self):
            nonlocal closed
            closed = True

    graph_database = SimpleNamespace(
        driver=lambda _uri, auth: FailingDriver(),
    )
    monkeypatch.setattr(health, "AsyncGraphDatabase", graph_database)
    settings = SimpleNamespace(
        NEO4J_URI="neo4j://graph.example.test:7687",
        NEO4J_DATABASE="neo4j",
        NEO4J_USERNAME="reader",
        NEO4J_PASSWORD="password",
    )

    with pytest.raises(RuntimeError, match="query failed"):
        await health.check_neo4j(settings)

    assert closed is True


def test_application_mounts_health_endpoints(test_app):
    paths = {route.path for route in test_app.routes}

    assert "/health/live" in paths
    assert "/health/ready" in paths
