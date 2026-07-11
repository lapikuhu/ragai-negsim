import pytest
from sqlmodel import select


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.postgres
@pytest.mark.startup
async def test_startup_seed_is_idempotent_against_migrated_postgres(
    migrated_postgres_db,
):
    """
    Test that the startup_seed function is idempotent and correctly seeds the
    PostgreSQL database with the expected roles and admin user.
    """
    from app.core.config import settings
    from app.db.db import AsyncSessionLocal, startup_seed
    from app.models.user_roles import Role, UserRoleLink
    from app.models.users import User

    await startup_seed()
    await startup_seed()

    async with AsyncSessionLocal() as session:
        roles_result = await session.exec(select(Role))
        roles = roles_result.all()
        admin_result = await session.exec(
            select(User).where(User.username == settings.ADMIN_USERNAME)
        )
        admin_user = admin_result.one()
        admin_role_result = await session.exec(
            select(Role).where(Role.name == "admin")
        )
        admin_role = admin_role_result.one()
        link_result = await session.exec(
            select(UserRoleLink).where(
                UserRoleLink.user_id == admin_user.id,
                UserRoleLink.role_id == admin_role.id,
            )
        )
        admin_links = link_result.all()

    role_names = {role.name for role in roles}
    assert set(settings.FIXED_ROLES) <= role_names
    assert len([role for role in roles if role.name == "admin"]) == 1
    assert admin_user.username == settings.ADMIN_USERNAME
    assert len(admin_links) == 1