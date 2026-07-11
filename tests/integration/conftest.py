import os
from pathlib import Path
import sys
from typing import Generator
from uuid import uuid4

from neo4j import GraphDatabase
from neo4j import Driver
import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

_REQUIRED_INTEGRATION_SETTINGS = {
    "ASYNC_DATABASE_URL": (
        "postgresql+asyncpg://postgres:change_me_postgres@127.0.0.1:5432/negsim"
    ),
    "ADMIN_USERNAME": "test-admin",
    "ADMIN_EMAIL": "test-admin@example.test",
    "ADMIN_PASSWORD": "test-password",
    "NEO4J_URI": "bolt://127.0.0.1:7687",
    "NEO4J_USERNAME": "neo4j",
    "NEO4J_PASSWORD": "change_me_neo4j",
    "NEO4J_DATABASE": "neo4j",
    "SECRET_KEY": "test-secret-key",
    "ALGORITHM": "HS256",
    "OPENAI_API_KEY": "test-openai-api-key",
}

for name, value in _REQUIRED_INTEGRATION_SETTINGS.items():
    os.environ.setdefault(name, value)


@pytest.fixture(scope="session")
def neo4j_cfg() -> dict[str, str]:
    from app.airag.knowledge_graph.connection import (
        resolve_neo4j_database,
        resolve_neo4j_uri,
    )

    return {
        "uri": resolve_neo4j_uri(os.environ["NEO4J_URI"]),
        "username": os.environ["NEO4J_USERNAME"],
        "password": os.environ["NEO4J_PASSWORD"],
        "database": resolve_neo4j_database(os.environ.get("NEO4J_DATABASE")),
    }


@pytest.fixture(scope="session")
def neo4j_driver(neo4j_cfg: dict[str, str]) -> Generator[Driver, None, None]:
    driver = GraphDatabase.driver(
        neo4j_cfg["uri"],
        auth=(neo4j_cfg["username"], neo4j_cfg["password"]),
    )
    try:
        driver.verify_connectivity()
    except Exception as exc:
        driver.close()
        pytest.skip(f"Neo4j is not available for integration tests: {exc}")

    try:
        yield driver
    finally:
        driver.close()


@pytest.fixture
def scoped_neo4j_store(neo4j_cfg: dict[str, str], neo4j_driver: Driver):
    from app.airag.knowledge_graph.scoped_store import ScopedNeo4jPropertyGraphStore

    store = ScopedNeo4jPropertyGraphStore(
        graph_id=9001,
        generation=f"it-{uuid4().hex[:12]}",
        username=neo4j_cfg["username"],
        password=neo4j_cfg["password"],
        url=neo4j_cfg["uri"],
        database=neo4j_cfg["database"],
    )
    store.delete_generation()

    try:
        yield store
    finally:
        store.delete_generation()