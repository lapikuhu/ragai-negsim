"""The application's liveness and readiness routes."""

import asyncio
import logging
from collections.abc import Awaitable

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from neo4j import AsyncGraphDatabase
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.airag.knowledge_graph.connection import (
    resolve_neo4j_database,
    resolve_neo4j_uri,
)
from app.core.config import Settings
from app.core.dependencies import SessionDep, SettingsDep


logger = logging.getLogger(__name__)
READINESS_TIMEOUT_SECONDS = 2.0

# Instantiate the APIRouter with a prefix and tags for the health check routes
router = APIRouter(prefix="/health", tags=["health"])

### ---------------------------- HELPERS --------------------------- ###
async def check_postgres(session: AsyncSession) -> None:
    """
    Verify that PostgreSQL accepts a lightweight query.

    Args:
        session: The database session.
    Raises:
        Exception: If the PostgreSQL query fails or the connection cannot 
    be established.
    """
    await session.exec(text("SELECT 1"))


async def check_neo4j(settings: Settings) -> None:
    """
    Verify that Neo4j accepts a lightweight query.
    
    Args:
        settings: The application settings containing Neo4j connection 
        info.
    Raises:
        Exception: If the Neo4j query fails or the connection cannot be 
    established.
    """
    driver = AsyncGraphDatabase.driver(
        resolve_neo4j_uri(settings.NEO4J_URI),
        auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
    )
    try:
        await driver.execute_query(
            "RETURN 1",
            database_=resolve_neo4j_database(settings.NEO4J_DATABASE),
        )
    finally:
        await driver.close()


async def _dependency_status(
    dependency_name: str,
    check: Awaitable[None],
) -> str:
    """
    Check the status of a dependency by running its check function with a 
    timeout.

    Args:
        dependency_name: The name of the dependency to check.
        check: An awaitable function that performs the dependency check.
    Returns:
        A string indicating the status of the dependency: "ok" if the check
    passed, or "unavailable" if the check failed or timed out.
    """
    try:
        await asyncio.wait_for(check, timeout=READINESS_TIMEOUT_SECONDS)
    except Exception:
        logger.exception("%s readiness check failed", dependency_name)
        return "unavailable"
    return "ok"

async def _readiness_result(
    session: AsyncSession,
    settings: Settings,
) -> tuple[dict, int]:
    """
    Check the readiness status of the application's dependencies.

    Args:
        session: The database session.
        settings: The application settings.
    Returns:
        A tuple containing a dictionary with the readiness status and 
    an HTTP status code.
    """
    postgres_status, neo4j_status = await asyncio.gather(
        _dependency_status("PostgreSQL", check_postgres(session)),
        _dependency_status("Neo4j", check_neo4j(settings)),
    )

    checks = {
        "postgres": postgres_status,
        "neo4j": neo4j_status,
    }
    failed = [
        name
        for name, result in (
            ("PostgreSQL", postgres_status),
            ("Neo4j", neo4j_status),
        )
        if result == "unavailable"
    ]

    if not failed:
        return {"status": "ready", "checks": checks}, status.HTTP_200_OK

    message = (
        f"{failed[0]} connection check failed"
        if len(failed) == 1
        else "PostgreSQL and Neo4j connection checks failed"
    )
    return {
        "status": "not_ready",
        "checks": checks,
        "message": message,
    }, status.HTTP_503_SERVICE_UNAVAILABLE


### -------------------------- LIVE ENDPOINT ----------------------- ###
@router.get("/live", 
            status_code=status.HTTP_200_OK)
def liveness_check():
    """
    Simple liveness check endpoint.

    Returns a JSON response indicating the application is alive.
    """
    return {"status": "alive"}

### -------------------------- READY ENDPOINT ---------------------- ###
@router.get("/ready", 
            status_code=status.HTTP_200_OK)
async def readiness_check(session: SessionDep, 
                          settings: SettingsDep):
    """
    Check the application's hard infrastructure dependencies.

    Args:
        session: The database session.
        settings: The application settings.
    Returns:
        A JSON response indicating the readiness status of the 
        application. Both PostgreSQL and Neo4j connection checks are 
        performed.
    """
    payload, status_code = await _readiness_result(session, settings)
    return JSONResponse(status_code=status_code, content=payload)

### -------------------------- GENERAL HEALTH ENDPOINT (BOTH) --------------------- ###
@router.get("/",
            status_code=status.HTTP_200_OK)
async def health_check(session: SessionDep,
                       settings: SettingsDep):
    """
    Check the application's liveness and readiness.

    Args:
        session: The database session.
        settings: The application settings.
    Returns:
        A JSON response indicating the health status of the application.
    """
    readiness, status_code = await _readiness_result(session, settings)

    return JSONResponse(
        status_code=status_code,
        content={
            "live": liveness_check(),
            "ready": readiness,
        },
    )
