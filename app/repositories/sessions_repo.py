from sqlalchemy import or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.sessions import Session as UserSession
from app.models.simulations import Simulation
from app.repositories.helpers import commit_and_refresh, commit_delete, utc_now
from app.schemas.sessions_schemas import (
    SessionCreate,
    SessionEnd,
    SessionHeartbeat,
    SessionUpdate,
)


async def get_session_by_id(
    session_id: int,
    session: AsyncSession,
) -> UserSession | None:
    """
    Retrieve a session by its ID.
    Args:
        session_id (int): The ID of the session to retrieve.
        session (AsyncSession): The database session for querying the session.
    Returns:
        UserSession | None: The retrieved session or None if not found.
    """
    return await session.get(UserSession, session_id)


async def get_session_by_token(
    session_token: str,
    session: AsyncSession,
) -> UserSession | None:
    """
    Retrieve a session by its token.
    Args:
        session_token (str): The token of the session to retrieve.
        session (AsyncSession): The database session for querying the session.
    Returns:
        UserSession | None: The retrieved session or None if not found.
    """
    result = await session.exec(
        select(UserSession).where(UserSession.session_token == session_token)
    )
    return result.first()


async def list_sessions(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    user_id: int | None = None,
    active: bool | None = None,
    expired: bool | None = None,
) -> list[UserSession]:
    """
    List sessions with optional filters for user ID, active status, and expiration status.
    Args:
        session (AsyncSession): The database session for querying sessions.
        skip (int): The number of sessions to skip for pagination.
        limit (int): The maximum number of sessions to return.
        user_id (int | None): Filter sessions by user ID.
        active (bool | None): Filter sessions by active status.
        expired (bool | None): Filter sessions by expiration status.
    Returns:
        list[UserSession]: A list of sessions matching the filters.
    """
    statement = select(UserSession)

    if user_id is not None:
        statement = statement.where(UserSession.user_id == user_id)

    now = utc_now()
    if active is True:
        statement = statement.where(UserSession.ended_at.is_(None))
        statement = statement.where(
            or_(UserSession.expires_at.is_(None), UserSession.expires_at > now)
        )
    elif active is False:
        statement = statement.where(
            or_(
                UserSession.ended_at.is_not(None),
                UserSession.expires_at <= now,
            )
        )

    if expired is True:
        statement = statement.where(UserSession.expires_at <= now)
    elif expired is False:
        statement = statement.where(
            or_(UserSession.expires_at.is_(None), UserSession.expires_at > now)
        )

    statement = statement.offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def session_has_simulations(
    session_id: int,
    session: AsyncSession,
) -> bool:
    """
    Check if a session has any associated simulations.
    Args:
        session_id (int): The ID of the session to check.
        session (AsyncSession): The database session for querying simulations.
    Returns:
        bool: True if the session has simulations, False otherwise.
    """
    result = await session.exec(
        select(Simulation.id).where(Simulation.session_id == session_id).limit(1)
    )
    return result.first() is not None


async def create_session(
    session_in: SessionCreate,
    session: AsyncSession,
) -> UserSession:
    """
    Create a new session.
    Args:
        session_in (SessionCreate): The session data to create.
        session (AsyncSession): The database session for querying and committing the session.
    Returns:
        UserSession: The created session.
    """
    user_session = UserSession(**session_in.model_dump())
    return await commit_and_refresh(session, user_session)

# CHECK purpose of patching a session
async def update_session(
    user_session: UserSession,
    session_in: SessionUpdate,
    session: AsyncSession,
) -> UserSession:
    """
    Update an existing session with new data.
    Args:
        user_session (UserSession): The session to update.
        session_in (SessionUpdate): The new session data.
        session (AsyncSession): The database session for querying and committing the session.
    Returns:
        UserSession: The updated session.
    """
    update_data = session_in.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(user_session, field_name, value)

    return await commit_and_refresh(session, user_session)

# CHECK
async def heartbeat_session(
    user_session: UserSession,
    heartbeat_in: SessionHeartbeat,
    session: AsyncSession,
) -> UserSession:
    """
    Update the last seen timestamp of a session.
    Args:
        user_session (UserSession): The session to update.
        heartbeat_in (SessionHeartbeat): The heartbeat data containing the new last seen timestamp.
        session (AsyncSession): The database session for querying and committing the session.
    Returns:
        UserSession: The updated session.
    """
    user_session.last_seen_at = heartbeat_in.last_seen_at
    return await commit_and_refresh(session, user_session)


async def end_session(
    user_session: UserSession,
    end_in: SessionEnd,
    session: AsyncSession,
) -> UserSession:
    """
    End a session by setting its ended_at timestamp.
    Args:
        user_session (UserSession): The session to end.
        end_in (SessionEnd): The end data containing the ended_at timestamp.
        session (AsyncSession): The database session for querying and 
            committing the session.
    Returns:
        UserSession: The ended session.
    """
    user_session.ended_at = end_in.ended_at
    return await commit_and_refresh(session, user_session)


async def delete_session(
    user_session: UserSession,
    session: AsyncSession,
) -> None:
    """
    Delete a session if it has no associated simulations.
    Args:
        user_session (UserSession): The session to delete.
        session (AsyncSession): The database session for querying and 
            committing the deletion.
    Returns:
        None
    Raises:
        ValueError: If the session has not been persisted or if it has associated simulations.
    """
    if user_session.id is None:
        raise ValueError("Session must be persisted before deletion")

    if await session_has_simulations(user_session.id, session):
        raise ValueError("Cannot delete session with simulations")

    await commit_delete(session, user_session)
