### ----------------------------- USER ROUTERS ------------------------- ###
# Handle HTTP requests related to users. Routes call services to perform
# business logic and return responses. Repositories are not called directly.

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from core.dependencies import AdminDep, CurrentUserDep, SessionDep
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


router = APIRouter(prefix="/users", tags=["users"])


def to_user_read(user) -> UserRead:
    """Convert a user model to a UserRead schema."""
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
    message = str(exc)
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)
    if message == "User not found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


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
    """Create a new user. Admins only."""
    try:
        user = await users_service.create_user_service(user_data, session, admin_user)
        return UserCreatedResponse(ok=True, user=to_user_read(user))
    except (ValueError, PermissionError) as exc:
        _raise_user_service_error(exc)


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
) -> Token:
    """Authenticate user and return an access token."""
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
    """Get the current authenticated user's information."""
    return to_user_read(current_user)


@router.patch("/me/password", response_model=UserRead, status_code=status.HTTP_200_OK)
async def change_own_password(
    password_data: UserPasswordChange,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> UserRead:
    """Change the current user's password after verifying the old password."""
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
    skip: int = 0,
    limit: int = 100,
) -> list[UserRead]:
    """Get a list of all users. Admins only."""
    try:
        users = await users_service.get_all_users_service(
            session,
            admin_user,
            skip=skip,
            limit=limit,
        )
        return [to_user_read(user) for user in users]
    except (ValueError, PermissionError) as exc:
        _raise_user_service_error(exc)


@router.get("/{username}", response_model=UserRead, status_code=status.HTTP_200_OK)
async def get_user_by_username(
    username: str,
    session: SessionDep,
    _admin_user: AdminDep,
) -> UserRead:
    """Get user information by username. Admins only."""
    user = await users_service.get_user_by_username_service(username, session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return to_user_read(user)


@router.patch("/{user_id}", response_model=UserRead, status_code=status.HTTP_200_OK)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    session: SessionDep,
    admin_user: AdminDep,
) -> UserRead:
    """Update user information. Admins only."""
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


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    session: SessionDep,
    admin_user: AdminDep,
) -> None:
    """Delete a user. Admins only."""
    try:
        await users_service.delete_user_service(user_id, session, admin_user)
    except (ValueError, PermissionError) as exc:
        _raise_user_service_error(exc)
