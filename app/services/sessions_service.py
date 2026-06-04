from datetime import timedelta
from secrets import token_urlsafe

from sqlmodel.ext.asyncio.session import AsyncSession

from core.config import settings
from models.sessions import Session as UserSession
from models.users import User
from repositories import sessions_repo, users_repo
from repositories.helpers import utc_now
from schemas.sessions_schemas import (
    SessionCreate,
    SessionCreateRequest,
    SessionEnd,
    SessionHeartbeat,
    SessionRead,
    SessionUpdate,
    SessionUpdateRequest,
)

# Check token ambiguity
def _generate_session_token() -> str:
    """
    Generate a secure session token.
    Returns:
        str: A secure session token.
    """
    return token_urlsafe(32)

# Check session behavior regarding expiration and heartbeat updates
def _session_expires_at():
    """
    Calculate the expiration time for a session.
    Returns:
        datetime: The expiration time for the session.
    """
    return utc_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


def _read_session(user_session: UserSession) -> SessionRead:
    """
    Convert a UserSession model to a SessionRead schema.
    Args:
        user_session (UserSession): The session model to convert.
    Returns:
        SessionRead: The converted session schema.
    """
    return SessionRead(
        id=user_session.id,
        user_id=user_session.user_id,
        created_at=user_session.created_at,
        expires_at=user_session.expires_at,
        last_seen_at=user_session.last_seen_at,
        ended_at=user_session.ended_at,
    )

# Candidate for helpers
async def _ensure_user_exists(
    user_id: int | None,
    session: AsyncSession,
) -> None:
    """
    Ensure that a user exists in the database.
    Args:
        user_id (int | None): The ID of the user to check.
        session (AsyncSession): The database session for querying the user.
    Raises:
        ValueError: If the user does not exist.
    """
    if user_id is None:
        return

    user = await users_repo.get_user_by_id(user_id, session)
    if user is None:
        raise ValueError("User not found")


async def create_login_session_srvc(
    user: User,
    session: AsyncSession,
) -> UserSession:
    """
    Create a login session for a user.
    Args:
        user (User): The user for whom to create the session.
        session (AsyncSession): The database session for querying and committing the session.
    Returns:
        UserSession: The created session.
    Raises:
        ValueError: If the user has not been persisted.
    """
    if user.id is None:
        raise ValueError("User must be persisted before creating a session")

    now = utc_now()
    session_in = SessionCreate(
        user_id=user.id,
        session_token=_generate_session_token(),
        expires_at=_session_expires_at(),
        last_seen_at=now,
    )
    return await sessions_repo.create_session(session_in, session)


async def create_session_srvc(
    session_data: SessionCreateRequest,
    session: AsyncSession,
    _current_user: User,
) -> SessionRead:
    """
    Create a new session.
    Args:
        session_data (SessionCreateRequest): The session data to create.
        session (AsyncSession): The database session for querying and committing the session.
        _current_user (User): The current user creating the session.
    Returns:
        SessionRead: The created session.
    Raises:
        ValueError: If the user does not exist.
    """
    await _ensure_user_exists(session_data.user_id, session)
    session_in = SessionCreate(
        **session_data.model_dump(),
        session_token=_generate_session_token(),
        last_seen_at=utc_now(),
    )
    created_session = await sessions_repo.create_session(session_in, session)
    return _read_session(created_session)


async def list_sessions_srvc(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    user_id: int | None = None,
    active: bool | None = None,
    expired: bool | None = None,
) -> list[SessionRead]:
    """
    List sessions with optional filters.
    Args:
        session (AsyncSession): The database session for querying sessions.
        skip (int): The number of sessions to skip for pagination.
        limit (int): The maximum number of sessions to return.
        user_id (int | None): The ID of the user to filter sessions by.
        active (bool | None): Whether to filter for active sessions.
        expired (bool | None): Whether to filter for expired sessions.
    Returns:
        list[SessionRead]: A list of session schemas.
    """
    sessions = await sessions_repo.list_sessions(
        session=session,
        skip=skip,
        limit=limit,
        user_id=user_id,
        active=active,
        expired=expired,
    )
    return [_read_session(user_session) for user_session in sessions]


async def get_session_srvc(
    user_session: UserSession,
) -> SessionRead:
    """
    Get a session by its model.
    Args:
        user_session (UserSession): The session model to convert.
    Returns:
        SessionRead: The converted session schema.
    """
    return _read_session(user_session)


async def update_session_srvc(
    user_session: UserSession,
    session_data: SessionUpdateRequest,
    session: AsyncSession,
) -> SessionRead:
    """
    Update an existing session.
    Args:
        user_session (UserSession): The session to update.
        session_data (SessionUpdateRequest): The new session data.
        session (AsyncSession): The database session for querying and 
            committing the session.
    Returns:
        SessionRead: The updated session.
    """
    session_in = SessionUpdate(**session_data.model_dump(exclude_unset=True))
    updated_session = await sessions_repo.update_session(
        user_session,
        session_in,
        session,
    )
    return _read_session(updated_session)


async def heartbeat_session_srvc(
    user_session: UserSession,
    heartbeat_data: SessionHeartbeat,
    session: AsyncSession,
) -> SessionRead:
    """
    Update the last seen timestamp of a session.
    Args:
        user_session (UserSession): The session to update.
        heartbeat_data (SessionHeartbeat): The heartbeat data containing 
            the new last seen timestamp.
        session (AsyncSession): The database session for querying and 
            committing the session.
    Returns:
        SessionRead: The updated session.
    """
    heartbeat_in = SessionHeartbeat(
        last_seen_at=heartbeat_data.last_seen_at or utc_now(),
    )
    updated_session = await sessions_repo.heartbeat_session(
        user_session,
        heartbeat_in,
        session,
    )
    return _read_session(updated_session)


async def end_session_srvc(
    user_session: UserSession,
    end_data: SessionEnd,
    session: AsyncSession,
) -> SessionRead:
    """
    End an existing session.
    Args:
        user_session (UserSession): The session to end.
        end_data (SessionEnd): The end data containing the ended timestamp.
        session (AsyncSession): The database session for querying and 
            committing the session.
    Returns:
        SessionRead: The ended session.
    """
    end_in = SessionEnd(ended_at=end_data.ended_at or utc_now())
    updated_session = await sessions_repo.end_session(user_session, end_in, session)
    return _read_session(updated_session)


async def delete_session_srvc(
    user_session: UserSession,
    session: AsyncSession,
) -> None:
    """
    Delete a session.
    Args:
        user_session (UserSession): The session to delete.
        session (AsyncSession): The database session for querying and 
            committing the session.
    """
    await sessions_repo.delete_session(user_session, session)
