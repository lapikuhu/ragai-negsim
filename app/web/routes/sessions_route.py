from fastapi import APIRouter, HTTPException, status

from core.dependencies import AdminDep, AdminSessionDep, Page, SessionDep
from schemas.sessions_schemas import (
    SessionCreateRequest,
    SessionEnd,
    SessionHeartbeat,
    SessionRead,
    SessionUpdateRequest,
)
from services import sessions_service

# Declare the router for session-related endpoints
router = APIRouter(prefix="/sessions", tags=["sessions"])


def _raise_session_service_error(exc: ValueError) -> None:
    """
    Helper function to raise appropriate HTTP exceptions based on 
    service errors.
    Args:
        exc (ValueError): The exception raised by the service layer.
    Returns:
        None
    Raises:
        HTTPException: The corresponding HTTP exception based on the error 
        message.
    """
    message = str(exc)
    if message == "User not found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=message,
    ) from exc

### ------------------------ SESSION CREATE ------------------------ ###
@router.post(
    "/",
    response_model=SessionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    session_data: SessionCreateRequest,
    session: SessionDep,
    admin_user: AdminDep,
) -> SessionRead:
    """
    Create a new session endpoint.
    Args:
        session_data (SessionCreateRequest): The session data to create.
        session (SessionDep): The database session dependency.
        admin_user (AdminDep): The admin user dependency.
    Returns:
        SessionRead: The created session.
    """
    try:
        return await sessions_service.create_session_srvc(
            session_data,
            session,
            admin_user,
        )
    except ValueError as exc:
        _raise_session_service_error(exc)

### ------------------------- LIST SESSIONS ------------------------ ###
@router.get(
    "/",
    response_model=list[SessionRead],
    status_code=status.HTTP_200_OK,
)
async def list_sessions(
    session: SessionDep,
    _admin_user: AdminDep,
    page: Page,
    user_id: int | None = None,
    active: bool | None = None,
    expired: bool | None = None,
) -> list[SessionRead]:
    """
    List sessions with optional filters.
    Args:
        session (SessionDep): The database session dependency.
        _admin_user (AdminDep): The admin user dependency.
        page (Page): The pagination parameters.
        user_id (int | None): The ID of the user to filter sessions by.
        active (bool | None): Whether to filter for active sessions.
        expired (bool | None): Whether to filter for expired sessions.
    Returns:
        list[SessionRead]: A list of session schemas.
    """
    return await sessions_service.list_sessions_srvc(
        session=session,
        skip=page["skip"],
        limit=page["limit"],
        user_id=user_id,
        active=active,
        expired=expired,
    )

### ----------------------- GET SESSION BY ID ---------------------- ###
@router.get(
    "/{session_id}",
    response_model=SessionRead,
    status_code=status.HTTP_200_OK,
)
async def get_session(
    user_session: AdminSessionDep,
) -> SessionRead:
    """
    Get a session by its ID.
    Args:
        user_session (AdminSessionDep): The admin session dependency.
    Returns:
        SessionRead: The session schema.
    """
    return await sessions_service.get_session_srvc(user_session)

### --------------------- UPDATE SESSION BY ID --------------------- ###
@router.patch(
    "/{session_id}",
    response_model=SessionRead,
    status_code=status.HTTP_200_OK,
)
async def update_session(
    session_data: SessionUpdateRequest,
    user_session: AdminSessionDep,
    session: SessionDep,
) -> SessionRead:
    """
    Update a session by its ID.
    Args:
        session_data (SessionUpdateRequest): The session data to update.
        user_session (AdminSessionDep): The admin session dependency.
        session (SessionDep): The database session dependency.
    Returns:
        SessionRead: The updated session.
    """
    try:
        return await sessions_service.update_session_srvc(
            user_session,
            session_data,
            session,
        )
    except ValueError as exc:
        _raise_session_service_error(exc)

### -------------------- HEARTBEAT SESSION BY ID ------------------- ###
@router.post(
    "/{session_id}/heartbeat",
    response_model=SessionRead,
    status_code=status.HTTP_200_OK,
)
async def heartbeat_session(
    heartbeat_data: SessionHeartbeat,
    user_session: AdminSessionDep,
    session: SessionDep,
) -> SessionRead:
    """
    Send a heartbeat for a session.
    Args:
        heartbeat_data (SessionHeartbeat): The heartbeat data.
        user_session (AdminSessionDep): The admin session dependency.
        session (SessionDep): The database session dependency.
    Returns:
        SessionRead: The updated session.
    """
    try:
        return await sessions_service.heartbeat_session_srvc(
            user_session,
            heartbeat_data,
            session,
        )
    except ValueError as exc:
        _raise_session_service_error(exc)

### ---------------------- END SESSION BY ID ----------------------- ###
@router.post(
    "/{session_id}/end",
    response_model=SessionRead,
    status_code=status.HTTP_200_OK,
)
async def end_session(
    end_data: SessionEnd,
    user_session: AdminSessionDep,
    session: SessionDep,
) -> SessionRead:
    """
    End a session.
    Args:
        end_data (SessionEnd): The end session data.
        user_session (AdminSessionDep): The admin session dependency.
        session (SessionDep): The database session dependency.
    Returns:
        SessionRead: The updated session.
    """
    try:
        return await sessions_service.end_session_srvc(
            user_session,
            end_data,
            session,
        )
    except ValueError as exc:
        _raise_session_service_error(exc)

### --------------------- DELETE SESSION BY ID --------------------- ###
@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_session(
    user_session: AdminSessionDep,
    session: SessionDep,
) -> None:
    """
    Delete a session.
    Args:
        user_session (AdminSessionDep): The admin session dependency.
        session (SessionDep): The database session dependency.
    Returns:
        None
    """
    try:
        await sessions_service.delete_session_srvc(user_session, session)
    except ValueError as exc:
        _raise_session_service_error(exc)
