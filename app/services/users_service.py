### ----------------------------- USER SERVICES------------------------- ###
# Business logic for user operations. Services are called by routes and
# call repositories to interact with the database.
# Defense in depth: Services also perform permission checks so route wiring is
# not the only authorization boundary.

from sqlmodel.ext.asyncio.session import AsyncSession

from core.security import create_access_token, verify_password
from models.users import User
from repositories import users_repo
from schemas.users_schemas import UserCreate, UserPasswordChange, UserUpdate


def _role_names_from_loaded_user(user: User) -> set[str]:
    roles = getattr(user, "roles", [])
    return {role.name for role in roles if role.name is not None}


async def _has_admin_privileges(user: User, session: AsyncSession) -> bool:
    if hasattr(user, "roles"):
        return "admin" in _role_names_from_loaded_user(user)

    if user.id is None:
        return False

    return await users_repo.user_has_role_by_id(user.id, "admin", session)


async def _ensure_admin(current_user: User, session: AsyncSession) -> None:
    if not await _has_admin_privileges(current_user, session):
        raise PermissionError("Admin role required")


async def create_user_service(
    user_data: UserCreate,
    session: AsyncSession,
    current_user: User,
) -> User:
    """Create a new user. Only admins can create users."""
    await _ensure_admin(current_user, session)
    return await users_repo.create_user(user_data, session)


async def update_user_service(
    user_id: int,
    user_data: UserUpdate,
    session: AsyncSession,
    current_user: User,
) -> User:
    """Update an existing user. Only admins can update users."""
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
    """Delete a user. Only admins can delete users."""
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
    """Change the current user's password after verifying the old password."""
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise ValueError("Current password is incorrect")

    update_data = UserUpdate(password=password_data.new_password)
    return await users_repo.update_user(current_user, update_data, session)


async def get_user_by_username_service(
    username: str,
    session: AsyncSession,
) -> User | None:
    """Get a user by username. Returns None if the user does not exist."""
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


async def get_user_by_id_service(
    user_id: int,
    session: AsyncSession,
) -> User | None:
    """Get a user by ID. Returns None if the user does not exist."""
    return await users_repo.get_user_by_id(user_id, session)


async def get_user_roles_by_id_service(
    user_id: int,
    session: AsyncSession,
) -> list[str] | None:
    """Get role names for a user by ID. Returns None if the user does not exist."""
    user = await users_repo.get_user_by_id(user_id, session)
    if user is None:
        return None
    return await users_repo.get_user_role_names(user_id, session)


async def user_login_service(
    username: str,
    password: str,
    session: AsyncSession,
) -> tuple[str, str]:
    """Authenticate user and return access token if valid."""
    user = await users_repo.get_user_by_username(username, session)
    if user and verify_password(password, user.hashed_password):
        access_token = create_access_token(username)
        token_type = "bearer"
        return access_token, token_type

    raise ValueError("Invalid username or password")
