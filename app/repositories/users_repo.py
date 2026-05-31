from collections.abc import Sequence

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
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


async def get_user_by_id(
    user_id: int,
    session: AsyncSession,
) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_username(
    username: str,
    session: AsyncSession,
) -> User | None:
    result = await session.exec(select(User).where(User.username == username))
    return result.first()


async def get_role_by_id(
    role_id: int,
    session: AsyncSession,
) -> Role | None:
    return await session.get(Role, role_id)


async def get_role_by_name(
    role_name: str,
    session: AsyncSession,
) -> Role | None:
    result = await session.exec(select(Role).where(Role.name == role_name))
    return result.first()


async def ensure_username_available(
    username: str,
    session: AsyncSession,
    exclude_user_id: int | None = None,
) -> None:
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
    result = await session.exec(select(UserRoleLink.role_id).where(UserRoleLink.user_id == user_id))
    return [role_id for role_id in result.all() if role_id is not None]


async def get_user_role_names(
    user_id: int,
    session: AsyncSession,
) -> list[str]:
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
    limit: int = 20,
    role_name: str | None = None,
    username_contains: str | None = None,
) -> list[User]:
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
    limit: int = 20,
) -> list[User]:
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
    return await list_users_by_role("student", session, skip=skip, limit=limit)


async def ensure_roles_exist(
    role_ids: Sequence[int],
    session: AsyncSession,
) -> None:
    for role_id in dict.fromkeys(role_ids):
        if await get_role_by_id(role_id, session) is None:
            raise ValueError(f"Role not found: {role_id}")


async def create_user(
    user_in: UserCreate,
    session: AsyncSession,
) -> User:
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
    result = await session.exec(statement.limit(1))
    return result.first() is not None


async def user_has_owned_or_referenced_records(
    user_id: int,
    session: AsyncSession,
) -> bool:
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