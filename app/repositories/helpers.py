"""Helper functions for repositories."""

from datetime import datetime, timezone
from typing import TypeVar
from sqlmodel.ext.asyncio.session import AsyncSession

# Define a generic type variable for SQLModel instances
# This allows us to create helper functions that can work with any SQLModel subclass.
ModelT = TypeVar("ModelT")


def utc_now() -> datetime:
    """Get the current UTC time as a timezone-aware datetime object.
    Args:
        None
    Returns:
        datetime: The current UTC time with timezone information.
    """
    return datetime.now(timezone.utc)


async def commit_and_refresh(
    session: AsyncSession,
    instance: ModelT,
) -> ModelT:
    """Commit the current transaction and refresh the instance from the database.
    Args:
        session (AsyncSession): The database session to use for committing and refreshing.
        instance (ModelT): The SQLModel instance to refresh after committing.
    Returns:
        ModelT: The refreshed instance after committing the transaction.
    """
    try:
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
        return instance
    except Exception:
        await session.rollback()
        raise


async def commit_delete(
    session: AsyncSession,
    instance: ModelT,
) -> None:
    """Delete the instance from the database and commit the transaction.
    Args:
        session (AsyncSession): The database session to use for deleting the instance.
        instance (ModelT): The SQLModel instance to delete.
    Returns:
        None
    """
    try:
        await session.delete(instance)
        await session.commit()
    except Exception:
        await session.rollback()
        raise