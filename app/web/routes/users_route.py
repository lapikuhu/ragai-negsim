### ----------------------------- USER ROUTERS ------------------------- ###
# Handle HTTP requests related to users. Routes call services to perform
# business logic and return responses. Repositories are not called directly.

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from core.dependencies import AdminDep, CurrentUserDep, Page, SessionDep
from schemas.users_schemas import (
    RoleRead,
    Token,
    UserCreate,
    UserCreatedResponse,
    UserPasswordChange,
    UserRead,
    UserUpdate,
)
from services import users_service

# Create the router for the users domain endpoints.
router = APIRouter(prefix="/users", tags=["users"])


def to_user_read(user) -> UserRead:
    """
    Convert a user model to a UserRead schema.
    Args:
        user: The user model to convert.
    Returns:
        UserRead: The converted UserRead schema.
    """
    return UserRead(
        id=user.id,
        username=user.username,
        roles=[
            RoleRead(id=role.id, name=role.name)
            for role in getattr(user, "roles", [])
            if role.id is not None
        ],
    )


def _raise_user_service_error(exc: ValueError | PermissionError) -> None:
    """
    Raise an HTTPException based on the type of error.
    Args:
        exc (ValueError | PermissionError): The exception to handle.
    Raises:
        HTTPException: The corresponding HTTP exception.
    """
    message = str(exc)
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)
    if message == "User not found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

###--------------------------- CREATE USER ------------------------- ###
@router.post(
    "/register",
    response_model=UserCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    user_data: UserCreate,
    session: SessionDep,
    admin_user: AdminDep,
) -> UserCreatedResponse:
    """
    Create a new user. Admins only.
    Args:
        user_data (UserCreate): The data for the new user.
        session (SessionDep): The database session for any necessary queries.
        admin_user (AdminDep): The current admin user performing the operation.
    Returns:
        UserCreatedResponse: The response containing the created user.
    """
    try:
        user = await users_service.create_user_service(user_data, session, admin_user)
        return UserCreatedResponse(ok=True, user=to_user_read(user))
    except (ValueError, PermissionError) as exc:
        _raise_user_service_error(exc)

###--------------------------- LOGIN USER ------------------------- ###

@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
) -> Token:
    """Authenticate user and return an access token.
    Args:
        form_data (OAuth2PasswordRequestForm): The form data containing the username and password.
        session (SessionDep): The database session for any necessary queries.
    Returns:
        Token: The access token and token type.
    Raises:
        HTTPException: If the username or password is invalid.
    """
    try:
        access_token, token_type = await users_service.user_login_service(
            form_data.username,
            form_data.password,
            session=session,
        )
        return Token(access_token=access_token, token_type=token_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/me", response_model=UserRead, status_code=status.HTTP_200_OK)
async def get_me_user(current_user: CurrentUserDep) -> UserRead:
    """
    Get the current authenticated user's information.
    Args:
        current_user (CurrentUserDep): The current authenticated user.
    Returns:
        UserRead: The current user's information.
    """
    return to_user_read(current_user)

###----------------------- CHANGE OWN PASSWORD --------------------- ###
@router.patch("/me/password", response_model=UserRead, status_code=status.HTTP_200_OK)
async def change_own_password(
    password_data: UserPasswordChange,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> UserRead:
    """
    Change the current user's password after verifying the old password.
    Args:
        password_data (UserPasswordChange): The data for the password change.
        session (SessionDep): The database session for any necessary queries.
        current_user (CurrentUserDep): The current authenticated user.
    Returns:
        UserRead: The updated user information.
    """
    try:
        user = await users_service.change_own_password_service(
            password_data,
            session,
            current_user,
        )
        return to_user_read(user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/", response_model=list[UserRead], status_code=status.HTTP_200_OK)
async def get_all_users(
    session: SessionDep,
    admin_user: AdminDep,
    page: Page, # Pagination parameters containing skip and limit.
) -> list[UserRead]:
    """
    Get a list of all users. Admins only.
    Args:
        session (SessionDep): The database session for any necessary queries.
        admin_user (AdminDep): The current admin user performing the operation.
        page (Page): Pagination parameters containing skip and limit.
    Returns:
        list[UserRead]: A list of user information.
    Raises:
        PermissionError: If the current user is not an admin.
        ValueError: If there is an error retrieving the users."""
    try:
        users = await users_service.get_all_users_service(
            session,
            admin_user,
            skip=page["skip"],
            limit=page["limit"],
        )
        return [to_user_read(user) for user in users]
    except (ValueError, PermissionError) as exc:
        _raise_user_service_error(exc)

### ---------------------- GET USER BY USERNAME -------------------- ###
@router.get("/{username}", response_model=UserRead, status_code=status.HTTP_200_OK)
async def get_user_by_username(
    username: str,
    session: SessionDep,
    _admin_user: AdminDep,
) -> UserRead:
    """
    Get user information by username. Admins only.
    Args:
        username (str): The username of the user to retrieve.
        session (SessionDep): The database session for any necessary queries.
        _admin_user (AdminDep): The current admin user performing the 
            operation (not used but required for admin check).
    Returns:
        UserRead: The user information.
    Raises:
        HTTPException: If the user is not found or if there is an error retrieving the user
    """
    user = await users_service.get_user_by_username_service(username, session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return to_user_read(user)

### -------------------- UPDATE USER (ADMIN ONLY) ------------------ ###
@router.patch("/{user_id}", response_model=UserRead, status_code=status.HTTP_200_OK)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    session: SessionDep,
    admin_user: AdminDep,
) -> UserRead:
    """
    Update user information. Admins only.
    Args:
        user_id (int): The ID of the user to update.
        user_data (UserUpdate): The data to update the user with.
        session (SessionDep): The database session for any necessary queries.
        admin_user (AdminDep): The current admin user performing the operation.
    Returns:
        UserRead: The updated user information.
    Raises:
        HTTPException: If the user is not found or if there is an error updating the user.
    """
    try:
        user_update = await users_service.update_user_service(
            user_id,
            user_data,
            session,
            admin_user,
        )
        return to_user_read(user_update)
    except (ValueError, PermissionError) as exc:
        _raise_user_service_error(exc)

### -------------------- DELETE USER (ADMIN ONLY) ------------------ ###
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    session: SessionDep,
    admin_user: AdminDep,
) -> None:
    """
    Delete a user. Admins only.
    Args:
        user_id (int): The ID of the user to delete.
        session (SessionDep): The database session for any necessary queries.
        admin_user (AdminDep): The current admin user performing the operation.
    Raises:
        HTTPException: If the user is not found or if there is an error deleting the user.
    """
    try:
        await users_service.delete_user_service(user_id, session, admin_user)
    except (ValueError, PermissionError) as exc:
        _raise_user_service_error(exc)
