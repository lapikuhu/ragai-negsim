import os
from pathlib import Path
import sys
from typing import Generator
from uuid import uuid4

from alembic import command
from alembic.config import Config
from neo4j import GraphDatabase
from neo4j import Driver
import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

# Get the root directory of the project (two levels up from this file)
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Set default environment variables for integration tests
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
def postgres_cfg() -> dict[str, str]:
    """
    Fixture for providing PostgreSQL config settings.
    """
    async_url = os.environ["ASYNC_DATABASE_URL"]
    return {
        "async_url": async_url,
        "sync_url": async_url.replace("+asyncpg", "+psycopg"),
    }


@pytest.fixture(scope="session")
def postgres_connectivity(postgres_cfg: dict[str, str]) -> None:
    """
    Fixture for verifying PostgreSQL sync and async connectivity.
    """
    sync_engine = create_engine(postgres_cfg["sync_url"], pool_pre_ping=True)
    try:
        with sync_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        pytest.skip(f"PostgreSQL is not available for integration tests: {exc}")
    finally:
        sync_engine.dispose()


@pytest.fixture(scope="session")
def migrated_postgres_db(
    postgres_cfg: dict[str, str],
    postgres_connectivity: None,
) -> dict[str, str]:
    """
    Fixture for applying Alembic migrations to a real PostgreSQL database.
    """
    alembic_cfg = Config(str(ROOT_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(ROOT_DIR / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", postgres_cfg["sync_url"])
    command.upgrade(alembic_cfg, "head")
    return postgres_cfg


@pytest_asyncio.fixture
async def migrated_async_engine(migrated_postgres_db: dict[str, str]):
    """
    Fixture for providing an async SQLAlchemy engine against migrated PostgreSQL.
    """
    engine = create_async_engine(migrated_postgres_db["async_url"], pool_pre_ping=True)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def neo4j_cfg() -> dict[str, str]:
    """
    Fixture for providing Neo4j config settings
    """
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
    """
    Fixture for providing a Neo4j driver instance
    Args:
        neo4j_cfg (dict[str, str]): Neo4j configuration settings
    Yields:
        Driver: Neo4j driver instance
    """
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
    """
    Fixture for providing a scoped Neo4j property graph store.
    """
    from app.airag.knowledge_graph.scoped_schema_store import (
        ScopedSchemaNeo4jPropertyGraphStore,
    )

    store = ScopedSchemaNeo4jPropertyGraphStore(
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
