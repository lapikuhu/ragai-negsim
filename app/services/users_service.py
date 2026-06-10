### ----------------------------- USER SERVICES------------------------- ###
# Business logic for user operations. Services are called by routes and
# call repositories to interact with the database.
# Defense in depth: Services also perform permission checks so route wiring is
# not the only authorization boundary.

from datetime import datetime

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import create_access_token, verify_password
from app.models.user_roles import Role
from app.models.users import User
from app.repositories import users_repo
from app.schemas.users_schemas import UserCreate, UserPasswordChange, UserUpdate
from app.services import sessions_service


def _role_names_from_loaded_user(user: User) -> set[str]:
    """
    Extracts the role names from a loaded user object.
    Args:
        user (User): The user object.
    Returns:
        set[str]: A set of role names.
    """
    roles = getattr(user, "roles", [])
    return {role.name for role in roles if role.name is not None}


async def _has_admin_privileges(user: User, session: AsyncSession) -> bool:
    """
    Helper function to check if a user has admin privileges.
    Args:
        user (User): The user to check.
        session (AsyncSession): The database session for any necessary queries.
    Returns:
        bool: True if the user has admin privileges, False otherwise.
    """
    if hasattr(user, "roles"):
        return "admin" in _role_names_from_loaded_user(user)

    if user.id is None:
        return False

    return await users_repo.user_has_role_by_id(user.id, "admin", session)


async def _ensure_admin(current_user: User, session: AsyncSession) -> None:
    """
    Ensures that the current user has admin privileges.
    Args:
        current_user (User): The user to check.
        session (AsyncSession): The database session for any necessary queries.
    Raises:
        PermissionError: If the user does not have admin privileges.
    """
    if not await _has_admin_privileges(current_user, session):
        raise PermissionError("Admin role required")


async def create_user_service(
    user_data: UserCreate,
    session: AsyncSession,
    current_user: User,
) -> User:
    """
    Create a new user. Only admins can create users.
    Args:
        user_data (UserCreate): The data for the new user.
        session (AsyncSession): The database session for any necessary queries.
        current_user (User): The user performing the operation.
    Returns:
        User: The newly created user.
    """
    await _ensure_admin(current_user, session)
    return await users_repo.create_user(user_data, session)


async def update_user_service(
    user_id: int,
    user_data: UserUpdate,
    session: AsyncSession,
    current_user: User,
) -> User:
    """
    Update an existing user. Only admins can update users.
    Args:
        user_id (int): The ID of the user to update.
        user_data (UserUpdate): The data to update the user with.
        session (AsyncSession): The database session for any necessary queries.
        current_user (User): The user performing the operation.
    Returns:
        User: The updated user.
    """
    await _ensure_admin(current_user, session)

    user = await users_repo.get_user_by_id(user_id, session)
    if user is None:
        raise ValueError("User not found")

    update_payload = user_data.model_dump(exclude_unset=True, exclude={"role_ids"})
    if update_payload:
        user = await users_repo.update_user(user, UserUpdate(**update_payload), session)

    if user_data.role_ids is not None:
        user = await users_repo.replace_user_roles(user, user_data.role_ids, session)

    return user


async def delete_user_service(
    user_id: int,
    session: AsyncSession,
    current_user: User,
) -> None:
    """
    Delete a user. Only admins can delete users.
    Args:
        user_id (int): The ID of the user to delete.
        session (AsyncSession): The database session for any necessary queries.
        current_user (User): The user performing the operation.
    Raises:
        ValueError: If the user does not exist.
    """
    await _ensure_admin(current_user, session)

    user = await users_repo.get_user_by_id(user_id, session)
    if user is None:
        raise ValueError("User not found")

    await users_repo.delete_user(user, session, current_admin_id=current_user.id)


async def change_own_password_service(
    password_data: UserPasswordChange,
    session: AsyncSession,
    current_user: User,
) -> User:
    """
    Change the current user's password after verifying the old password.
    Args:
        password_data (UserPasswordChange): The data for the password change.
        session (AsyncSession): The database session for any necessary queries.
        current_user (User): The user performing the operation.
    Returns:
        User: The updated user.
    """
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise ValueError("Current password is incorrect")

    update_data = UserUpdate(password=password_data.new_password)
    return await users_repo.update_user(current_user, update_data, session)


async def get_user_by_username_service(
    username: str,
    session: AsyncSession,
) -> User | None:
    """
    Get a user by username. Returns None if the user does not exist.
    Args:
        username (str): The username to search for.
        session (AsyncSession): The database session for any necessary queries.
    Returns:
        User | None: The user if found, or None if not found.
    """
    return await users_repo.get_user_by_username(username, session)


async def get_all_users_service(
    session: AsyncSession,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
) -> list[User]:
    """Get a list of users. Only admins can list users."""
    await _ensure_admin(current_user, session)
    return await users_repo.list_users(session, skip=skip, limit=limit)


async def list_roles_service(
    session: AsyncSession,
    current_user: User,
) -> list[Role]:
    """List assignable roles. Only admins can list role options."""
    await _ensure_admin(current_user, session)
    return await users_repo.list_roles(session)


async def get_user_by_id_service(
    user_id: int,
    session: AsyncSession,
) -> User | None:
    """
    Get a user by ID. Returns None if the user does not exist.
    Args:
        user_id (int): The ID of the user to retrieve.
        session (AsyncSession): The database session for any necessary queries.
    Returns:
        User | None: The user if found, or None if not found.
    """
    return await users_repo.get_user_by_id(user_id, session)


async def get_user_roles_by_id_service(
    user_id: int,
    session: AsyncSession,
) -> list[str] | None:
    """
    Get role names for a user by ID. Returns None if the user does not exist.
    Args:
        user_id (int): The ID of the user to retrieve roles for.
        session (AsyncSession): The database session for any necessary queries.
    Returns:
        list[str] | None: The list of role names if the user is found, or None if not found.
    """
    user = await users_repo.get_user_by_id(user_id, session)
    if user is None:
        return None
    return await users_repo.get_user_role_names(user_id, session)


async def user_login_service(
    username: str,
    password: str,
    session: AsyncSession,
) -> tuple[str, str, int | None, datetime | None]:
    """
    Authenticate user and return access token if valid.
    Args:
        username (str): The username of the user trying to log in.
        password (str): The plaintext password provided by the user.
        session (AsyncSession): The database session for any necessary queries.
    Returns:
        tuple[str, str]: A tuple containing the access token and token type.
    Raises:
        ValueError: If the username or password is invalid.
    """
    user = await users_repo.get_user_by_username(username, session)
    if user and verify_password(password, user.hashed_password):
        user_session = await sessions_service.create_login_session_srvc(user, session)
        access_token = create_access_token(username, session_id=user_session.id)
        token_type = "bearer"
        return access_token, token_type, user_session.id, user_session.expires_at

    raise ValueError("Invalid username or password")
