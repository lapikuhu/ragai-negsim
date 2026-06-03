### ----------------------------- USER SERVICES------------------------- ###
# Business logic for user operations. Services are called by routes and 
# call repositories to interact with the database.
# Defense in depth: Services also perform additional checks to ensure that 
# only users with the right permissions can perform certain actions. 

from models.users import User
from models.user_roles import Role
from repositories import users_repo
from schemas.users_schemas import UserCreate, UserIsAdminResponse, UserUpdate
from core.security import hash_password, verify_password, create_access_token
from db import AsyncSession


def _has_admin_privileges(user: UserIsAdminResponse | User) -> bool:
    roles = getattr(user, "roles", [])
    role_names = {role.name if hasattr(role, "name") else role for role in roles}
    return bool(user.is_admin or "admin" in role_names)


async def create_user_service(user_data: UserCreate, session: AsyncSession, cur_user_is_admin: UserIsAdminResponse) -> User:
    """Create a new user. Only admins can create other users.
    Args:
        user_data (UserCreate): Data for the new user.
        cur_user_is_admin (UserIsAdminResponse): Whether the user creating the new user is an admin.
        session (AsyncSession): Database session.
    Returns:
        User: The created user.
    Raises:
        ValueError: If the username already exists or if a non-admin tries to create an admin
  """
    if await users_repo.is_existing_user(user_data.username, session):
        raise ValueError("Username already exists")
    
    if not _has_admin_privileges(cur_user_is_admin):
        raise ValueError("Only admins can create other admin users")
    else:
        user = User(
            username=user_data.username,
            hashed_password=hash_password(user_data.password),
            is_admin=user_data.is_admin, # User data, not the current user!
            roles=[Role(name=role_name) for role_name in user_data.roles]
        )
    return await users_repo.create_user(user, session)

async def update_user_service(user_id: int, user_data: UserUpdate, session: AsyncSession, cur_user_is_admin: UserIsAdminResponse) -> User:
    """Update an existing user's information. Only admins can update users.
    Args:
        user_id (int): The ID of the user to update.
        user_data (UserUpdate): The new data for the user.
        session (AsyncSession): Database session.
        cur_user_is_admin (UserIsAdminResponse): Whether the user performing the update is an admin.
       
    Returns:
        User: The updated user.
    Raises:
        ValueError: If the user is not found, if the username already exists, or if a non-admin tries to update an admin
    """
    user = await users_repo.get_user_by_id(user_id, session)
    if not user:
        raise ValueError("User not found")
    
    if not _has_admin_privileges(cur_user_is_admin) and user.is_admin is True:
        raise ValueError("Only admins can update other admin users")
    
    if user_data.username is not None and user_data.username != user.username:
        if await users_repo.is_existing_user(user_data.username, session):
            raise ValueError("Username already exists")
        user.username = user_data.username

    if user_data.is_admin is not None:
        user.is_admin = user_data.is_admin

    if user_data.roles is not None:
        user.roles = [Role(name=role_name) for role_name in user_data.roles]
    
    return await users_repo.update_user(user, session)

async def delete_user_service(user_id: int, session: AsyncSession, cur_user_is_admin: UserIsAdminResponse) -> None:
    """Delete a user. Only admins can delete users.
    Args:
        user_id (int): The ID of the user to delete.
        session (AsyncSession): Database session.
        cur_user_is_admin (UserIsAdminResponse): Whether the user performing the deletion is an admin.
    Returns:
        None
    Raises:
        ValueError: If the user is not found or if a non-admin tries to delete an admin
    """
    user = await users_repo.get_user_by_id(user_id, session)
    if not user:
        raise ValueError("User not found")
    
    if not _has_admin_privileges(cur_user_is_admin) and user.is_admin is True:
        raise ValueError("Only admins can delete other admin users")
    await users_repo.delete_user(user, session)
    return None


async def get_user_by_username_service(username: str, session: AsyncSession) -> User | None:
    """Get a user by username. Returns None if the user does not exist.
    Args:
        username (str): The username of the user to retrieve.
        session (AsyncSession): Database session.
    Returns:
        User | None: The user instance if found, otherwise None.
    """
    return await users_repo.get_user_by_username(username, session)

async def get_all_users_service(session: AsyncSession, cur_user_is_admin: UserIsAdminResponse) -> list[User]:
    """Get a list of all users. Only admins can list users.
    Args:
        session (AsyncSession): Database session.
        cur_user_is_admin (UserIsAdminResponse): Whether the user performing the operation is an admin.
    Returns:
        list[User]: A list of all user instances.
    Raises:
        ValueError: If a non-admin tries to list users.
    """
    if not _has_admin_privileges(cur_user_is_admin):
        raise ValueError("Only admins can list users")
    return await users_repo.get_all_users(session)

async def get_user_by_id_service(user_id: int, session: AsyncSession) -> User | None:
    """Get a user by ID. Returns None if the user does not exist.
    Args:
        user_id (int): The ID of the user to retrieve.
        session (AsyncSession): Database session.
    Returns:
        User | None: The user instance if found, otherwise None.
    """
    return await users_repo.get_user_by_id(user_id, session)

async def get_user_roles_by_id_service(user_id: int, session: AsyncSession) -> list[str] | None:
    """Get the roles of a user by ID. Returns None if the user does not exist.
    Args:
        user_id (int): The ID of the user whose roles to retrieve.
        session (AsyncSession): Database session.
    Returns:
        list[str] | None: A list of role names if the user is found, otherwise None.
    """
    return await users_repo.get_user_roles_by_id(user_id, session)

async def user_login_service(username: str, password: str, session: AsyncSession) -> tuple[str, str] | None:
    """Authenticate user and return access token if valid.
    Args:
        username (str): Username of the user trying to log in.
        password (str): Password of the user trying to log in.
        session (AsyncSession): Database session.
    Returns:
        tuple[str, str]: Access token and token type if authentication is successful.
    Raises:
        ValueError: If authentication fails due to invalid username or password.
    """
    user = await users_repo.get_user_by_username(username, session)
    if user and verify_password(password, user.hashed_password):
        access_token = create_access_token(username)
        token_type = "bearer"
        return access_token, token_type
    else:
        raise ValueError("Invalid username or password")          

