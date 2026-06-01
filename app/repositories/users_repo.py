from collections.abc import Sequence
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# local imports
from core.security import get_password_hash
from models.corpus import Corpus
from models.counterpart_personas import CounterPartPersonas
from models.prompts import Prompt
from models.raw_documents import RawDocument
from models.scenarios import Scenario
from models.sessions import Session as UserSession
from models.simulations import Simulation
from models.user_roles import Role, UserRoleLink
from models.users import User
from repositories.helpers import commit_and_refresh
from schemas.users_schemas import UserCreate, UserUpdate

async def get_user_by_id(
    user_id: int,
    session: AsyncSession,
) -> User | None:
    """
    Get a user by their ID.
    Args:
        user_id: The ID of the user.
        session: The database session.
    Returns:
        The user if found, otherwise None.
    """
    return await session.get(User, user_id)


async def get_user_by_username(
    username: str,
    session: AsyncSession,
) -> User | None:
    """
    Get a user by their username.
    Args:
        username: The username of the user.
        session: The database session.
    Returns:
        The user if found, otherwise None.
    """
    result = await session.exec(select(User).where(User.username == username))
    return result.first()


async def get_role_by_id(
    role_id: int,
    session: AsyncSession,
) -> Role | None:
    """
    Get a role by its ID.
    Args:
        role_id: The ID of the role.
        session: The database session.
    Returns:
        The role if found, otherwise None.
    """
    return await session.get(Role, role_id)


async def get_role_by_name(
    role_name: str,
    session: AsyncSession,
) -> Role | None:
    """
    Get a role by its name.
    Args:
        role_name: The name of the role.
        session: The database session.
    Returns:
        The role if found, otherwise None.
    """
    result = await session.exec(select(Role).where(Role.name == role_name))
    return result.first()


async def ensure_username_available(
    username: str,
    session: AsyncSession,
    exclude_user_id: int | None = None,
) -> None:
    """
    Ensure that a username is available for use.
    Args:
        username: The username to check.
        session: The database session.
        exclude_user_id: Optional user ID to exclude from the check (useful for updates).
    Raises:
        ValueError: If the username is already taken.
    """
    existing_user = await get_user_by_username(username, session)
    if existing_user is None:
        return

    if exclude_user_id is not None and existing_user.id == exclude_user_id:
        return

    raise ValueError("Username already exists")


async def get_user_role_ids(
    user_id: int,
    session: AsyncSession,
) -> list[int]:
    """
    Get the IDs of roles assigned to a user.
    Args:
        user_id: The ID of the user.
        session: The database session.
    Returns:
        A list of role IDs assigned to the user.
    """
    result = await session.exec(select(UserRoleLink.role_id).where(UserRoleLink.user_id == user_id))
    return [role_id for role_id in result.all() if role_id is not None]


async def get_user_role_names(
    user_id: int,
    session: AsyncSession,
) -> list[str]:
    """
    Get the names of roles assigned to a user.
    Args:
        user_id: The ID of the user.
        session: The database session.
    Returns:
        A list of role names assigned to the user.
    """
    result = await session.exec(
        select(Role.name)
        .join(UserRoleLink, Role.id == UserRoleLink.role_id)
        .where(UserRoleLink.user_id == user_id)
    )
    return list(result.all())


async def user_has_role_by_id(
    user_id: int,
    role_name: str,
    session: AsyncSession,
) -> bool:
    """
    Check if a user has a specific role by role name.
    Args:
        user_id: The ID of the user.
        role_name: The name of the role to check.
        session: The database session.
    Returns:
        True if the user has the role, otherwise False.    
    """
    result = await session.exec(
        select(Role.id)
        .join(UserRoleLink, Role.id == UserRoleLink.role_id)
        .where(
            UserRoleLink.user_id == user_id,
            Role.name == role_name,
        )
        .limit(1)
    )
    return result.first() is not None


async def list_users(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 10,
    role_name: str | None = None,
    username_contains: str | None = None,
) -> list[User]:
    # TODO: Check pagination with pagination helper perhaps
    """
    List users with optional filtering by role and username.
    Args:
        session: The database session.
        skip: The number of records to skip for pagination.
        limit: The maximum number of records to return for pagination.
        role_name: Optional role name to filter users by.
        username_contains: Optional substring to filter usernames by.
    Returns:
        A list of users matching the specified criteria.

    """
    statement = select(User)

    if role_name is not None:
        statement = (
            statement
            .join(UserRoleLink, User.id == UserRoleLink.user_id)
            .join(Role, Role.id == UserRoleLink.role_id)
            .where(Role.name == role_name)
        )
    if username_contains is not None:
        statement = statement.where(User.username.contains(username_contains))

    statement = statement.offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def list_users_by_role(
    role_name: str,
    session: AsyncSession,
    skip: int = 0,
    limit: int = 10,
) -> list[User]:
    # TODO: Check functionality, probably redundant since list_users can be used with role_name filter
    """
    List users that have a specific role.
    Args:
        role_name: The name of the role to filter users by.
        session: The database session.
        skip: The number of records to skip for pagination.
        limit: The maximum number of records to return for pagination.
    Returns:
        A list of users with the specified role.
    """
    return await list_users(
        session=session,
        skip=skip,
        limit=limit,
        role_name=role_name,
    )


async def list_students(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
) -> list[User]:
    # TODO: Probably redundant since list_users_by_role can be used with "student"
    """
    List all users with the role of "student".
    Args:
        session: The database session.
        skip: The number of records to skip.
        limit: The maximum number of records to return.
    Returns:
        A list of users with the role of "student".
    """
    return await list_users_by_role("student", session, skip=skip, limit=limit)


async def ensure_roles_exist(
    role_ids: Sequence[int],
    session: AsyncSession,
) -> None:
    """
    Ensure that all roles in the given list exist.
    Args:
        role_ids: A list of role IDs to check.
        session: The database session.
    Raises:
        ValueError: If any role does not exist.
    """
    for role_id in dict.fromkeys(role_ids):
        if await get_role_by_id(role_id, session) is None:
            raise ValueError(f"Role not found: {role_id}")


async def create_user(
    user_in: UserCreate,
    session: AsyncSession,
) -> User:
    """
    Create a new user.
    Args:
        user_in: The data for the new user.
        session: The database session.
    Returns:
        The created user.
    """
    await ensure_username_available(user_in.username, session)
    await ensure_roles_exist(user_in.role_ids, session)
    user = User(
        username=user_in.username,
        hashed_password=get_password_hash(user_in.password),
    )

    try:
        session.add(user)
        await session.flush()

        if user.id is None:
            raise ValueError("User id was not generated")

        for role_id in dict.fromkeys(user_in.role_ids):
            session.add(UserRoleLink(user_id=user.id, role_id=role_id))

        await session.commit()
        await session.refresh(user)
        return user
    except Exception:
        await session.rollback()
        raise


async def update_user(
    user: User,
    user_in: UserUpdate,
    session: AsyncSession,
) -> User:
    """
    Update a user's information.
    Args:
        user: The user to update.
        user_in: The new data for the user.
        session: The database session.
    Returns:
        The updated user.
    """
    update_data = user_in.model_dump(exclude_unset=True)

    if "username" in update_data and update_data["username"] is not None:
        await ensure_username_available(update_data["username"], session, user.id)
        user.username = update_data["username"]

    if "password" in update_data and update_data["password"] is not None:
        user.hashed_password = get_password_hash(update_data["password"])

    return await commit_and_refresh(session, user)


async def get_user_role_link(
    user_id: int,
    role_id: int,
    session: AsyncSession,
) -> UserRoleLink | None:
    """
    Get the link between a user and a role.
    Args:
        user_id: The ID of the user.
        role_id: The ID of the role.
        session: The database session.
    Returns:
        The UserRoleLink if it exists, otherwise None.
    """
    result = await session.exec(
        select(UserRoleLink).where(
            UserRoleLink.user_id == user_id,
            UserRoleLink.role_id == role_id,
        )
    )
    return result.first()


async def assign_role_to_user(
    user: User,
    role_id: int,
    session: AsyncSession,
) -> UserRoleLink:
    """
    Assign a role to a user.
    Args:
        user: The user to whom the role is to be assigned.
        role_id: The ID of the role to assign.
        session: The database session.
    Returns:
        The UserRoleLink representing the assigned role.
    Raises:
        ValueError: If the user is not persisted or the role does not exist.
    """
    if user.id is None:
        raise ValueError("User must be persisted before assigning roles")

    if await get_role_by_id(role_id, session) is None:
        raise ValueError(f"Role not found: {role_id}")

    existing_link = await get_user_role_link(user.id, role_id, session)
    if existing_link is not None:
        return existing_link

    link = UserRoleLink(user_id=user.id, role_id=role_id)

    try:
        session.add(link)
        await session.commit()
        await session.refresh(link)
        return link
    except Exception:
        await session.rollback()
        raise


async def remove_role_from_user(
    user: User,
    role_id: int,
    session: AsyncSession,
) -> None:
    """
    Remove a role from a user.
    Args:
        user: The user from whom the role is to be removed.
        role_id: The ID of the role to remove.
        session: The database session.
    Raises:
        ValueError: If the user is not persisted or does not have the role.
    """
    if user.id is None:
        raise ValueError("User must be persisted before removing roles")

    link = await get_user_role_link(user.id, role_id, session)
    if link is None:
        raise ValueError("User does not have this role")

    try:
        await session.delete(link)
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def replace_user_roles(
    user: User,
    role_ids: list[int],
    session: AsyncSession,
) -> User:
    """
    Replace a user's roles with a new set of roles.
    Args:
        user: The user whose roles are to be replaced.
        role_ids: The list of role IDs to assign to the user.
        session: The database session.
    Returns:
        The updated user with the new roles.
    """
    if user.id is None:
        raise ValueError("User must be persisted before replacing roles")

    await ensure_roles_exist(role_ids, session)

    try:
        existing_links = await session.exec(
            select(UserRoleLink).where(UserRoleLink.user_id == user.id)
        )
        for link in existing_links.all():
            await session.delete(link)

        for role_id in dict.fromkeys(role_ids):
            session.add(UserRoleLink(user_id=user.id, role_id=role_id))

        await session.commit()
        await session.refresh(user)
        return user
    except Exception:
        await session.rollback()
        raise


async def _has_reference(
    statement,
    session: AsyncSession,
) -> bool:
    """
    Check if a statement has any references.
    Args:
        statement: The SQL statement to check.
        session: The database session.
    Returns:
        True if the statement has any references, otherwise False.
    """
    result = await session.exec(statement.limit(1))
    return result.first() is not None


async def user_has_owned_or_referenced_records(
    user_id: int,
    session: AsyncSession,
) -> bool:
    """
    Check if a user has any owned or referenced records.
    Args:
        user_id: The ID of the user.
        session: The database session.
    Returns:
        True if the user has any owned or referenced records, otherwise False.
    """
    checks = [
        select(Simulation.id).where(Simulation.user_id_owner == user_id),
        select(Simulation.id).where(Simulation.user_id_participant == user_id),
        select(Simulation.id).where(Simulation.teacher_id == user_id),
        select(UserSession.id).where(UserSession.user_id == user_id),
        select(Prompt.id).where(Prompt.owner_id == user_id),
        select(RawDocument.id).where(RawDocument.uploaded_by_user_id == user_id),
        select(Corpus.id).where(Corpus.created_by_user_id == user_id),
        select(Corpus.id).where(Corpus.last_edit_by_user_id == user_id),
        select(Scenario.id).where(Scenario.created_by_user_id == user_id),
        select(Scenario.id).where(Scenario.last_edit_by_user_id == user_id),
        select(CounterPartPersonas.id).where(CounterPartPersonas.created_by_user_id == user_id),
        select(CounterPartPersonas.id).where(CounterPartPersonas.last_edit_by_user_id == user_id),
    ]

    for statement in checks:
        if await _has_reference(statement, session):
            return True

    return False


async def ensure_user_deletable(
    user: User,
    session: AsyncSession,
    current_admin_id: int | None = None,
) -> None:
    """
    Ensure that a user can be deleted.
    Args:
        user: The user to check.
        session: The database session.
        current_admin_id: The ID of the current admin performing the deletion.
    Returns:
        None
    Raises:
        ValueError: If the user cannot be deleted.
    """
    if user.id is None:
        raise ValueError("User must be persisted before deletion")

    if current_admin_id is not None and current_admin_id == user.id:
        raise ValueError("Admins cannot delete their own user account")

    if await user_has_owned_or_referenced_records(user.id, session):
        raise ValueError("Cannot delete user with owned or referenced records")


async def delete_user(
    user: User,
    session: AsyncSession,
    current_admin_id: int | None = None,
) -> None:
    """
    Delete a user from the database.
    Args:
        user: The user to delete.
        session: The database session.
        current_admin_id: The ID of the current admin performing the deletion.
    Raises:
        ValueError: If the user cannot be deleted.
    """
    await ensure_user_deletable(user, session, current_admin_id=current_admin_id)

    if user.id is None:
        raise ValueError("User must be persisted before deletion")

    try:
        role_links = await session.exec(select(UserRoleLink).where(UserRoleLink.user_id == user.id))
        for role_link in role_links.all():
            await session.delete(role_link)

        await session.delete(user)
        await session.commit()
    except Exception:
        await session.rollback()
        raise