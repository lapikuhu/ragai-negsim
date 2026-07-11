import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.postgres
async def test_asyncpg_session_executes_against_migrated_postgres(
    migrated_async_engine,
):
    """
    Test that an asyncpg session can execute a simple query against the 
    migrated PostgreSQL database.
    """
    session_factory = async_sessionmaker(
        migrated_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        result = await session.exec(text("SELECT 1"))

    assert result.scalar_one() == 1