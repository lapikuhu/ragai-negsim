from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from schemas.users_schemas import UserCreate, UserPasswordChange, UserUpdate
from services import users_service


def _user(user_id=1, roles=None, hashed_password="hashed"):
    return SimpleNamespace(
        id=user_id,
        username=f"user-{user_id}",
        roles=roles or [],
        hashed_password=hashed_password,
    )


def _role(role_id, name):
    return SimpleNamespace(id=role_id, name=name)


def _admin(user_id=1):
    return _user(user_id=user_id, roles=[_role(1, "admin")])


def _student(user_id=2):
    return _user(user_id=user_id, roles=[_role(2, "student")])


def test_user_create_requires_at_least_one_role():
    with pytest.raises(ValidationError):
        UserCreate(username="alice", password="password123", role_ids=[])


def test_user_create_accepts_and_deduplicates_role_ids():
    user = UserCreate(username="alice", password="password123", role_ids=[1, 2, 1])

    assert user.role_ids == [1, 2]


def test_user_update_accepts_password_and_role_ids():
    user = UserUpdate(password="password123", role_ids=[3, 3])

    assert user.password == "password123"
    assert user.role_ids == [3]


@pytest.mark.asyncio
async def test_admin_create_user_with_multiple_roles(monkeypatch):
    captured = []

    async def fake_create_user(user_data, session):
        captured.append(user_data)
        return _user(user_id=10, roles=[_role(2, "student"), _role(3, "teacher")])

    monkeypatch.setattr(users_service.users_repo, "create_user", fake_create_user)

    user_data = UserCreate(username="alice", password="password123", role_ids=[2, 3])
    user = await users_service.create_user_service(user_data, object(), _admin())

    assert user.id == 10
    assert captured == [user_data]


@pytest.mark.asyncio
async def test_non_admin_create_update_delete_denied():
    user_data = UserCreate(username="alice", password="password123", role_ids=[2])

    with pytest.raises(PermissionError, match="Admin role required"):
        await users_service.create_user_service(user_data, object(), _student())

    with pytest.raises(PermissionError, match="Admin role required"):
        await users_service.update_user_service(10, UserUpdate(username="bob"), object(), _student())

    with pytest.raises(PermissionError, match="Admin role required"):
        await users_service.delete_user_service(10, object(), _student())


@pytest.mark.asyncio
async def test_admin_update_user_username_password_and_roles(monkeypatch):
    target = _user(user_id=10, roles=[_role(2, "student")])
    captured_update = []
    captured_roles = []

    async def fake_get_user_by_id(user_id, session):
        assert user_id == 10
        return target

    async def fake_update_user(user, user_data, session):
        captured_update.append(user_data)
        user.username = user_data.username
        return user

    async def fake_replace_user_roles(user, role_ids, session):
        captured_roles.append(role_ids)
        user.roles = [_role(role_id, f"role-{role_id}") for role_id in role_ids]
        return user

    monkeypatch.setattr(users_service.users_repo, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(users_service.users_repo, "update_user", fake_update_user)
    monkeypatch.setattr(users_service.users_repo, "replace_user_roles", fake_replace_user_roles)

    result = await users_service.update_user_service(
        10,
        UserUpdate(username="bob", password="password123", role_ids=[2, 3]),
        object(),
        _admin(),
    )

    assert result.username == "bob"
    assert captured_update[0].model_dump(exclude_unset=True) == {
        "username": "bob",
        "password": "password123",
    }
    assert captured_roles == [[2, 3]]


@pytest.mark.asyncio
async def test_owner_password_change_requires_current_password(monkeypatch):
    async def fake_update_user(user, user_data, session):
        user.hashed_password = user_data.password
        return user

    monkeypatch.setattr(users_service, "verify_password", lambda raw, hashed: raw == "old-password")
    monkeypatch.setattr(users_service.users_repo, "update_user", fake_update_user)

    current_user = _student()
    result = await users_service.change_own_password_service(
        UserPasswordChange(current_password="old-password", new_password="new-password"),
        object(),
        current_user,
    )

    assert result.hashed_password == "new-password"

    with pytest.raises(ValueError, match="Current password is incorrect"):
        await users_service.change_own_password_service(
            UserPasswordChange(current_password="wrong", new_password="new-password"),
            object(),
            current_user,
        )


@pytest.mark.asyncio
async def test_delete_propagates_repo_deletion_guards(monkeypatch):
    async def fake_get_user_by_id(user_id, session):
        return _user(user_id=user_id)

    async def fake_delete_user(user, session, current_admin_id=None):
        raise ValueError("Admins cannot delete their own user account")

    monkeypatch.setattr(users_service.users_repo, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(users_service.users_repo, "delete_user", fake_delete_user)

    with pytest.raises(ValueError, match="Admins cannot delete their own user account"):
        await users_service.delete_user_service(1, object(), _admin(user_id=1))


def test_users_router_is_mounted_and_static_routes_precede_username_route():
    from main import app

    paths = [route.path for route in app.routes]

    assert "/users/login" in paths
    assert "/users/register" in paths
    assert "/users/me/password" in paths
    assert paths.index("/users/me") < paths.index("/users/{username}")
