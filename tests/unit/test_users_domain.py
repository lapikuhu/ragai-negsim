from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.models.users import User
from app.repositories import users_repo
from app.schemas.users_schemas import UserCreate, UserPasswordChange, UserUpdate
from app.services import users_service


def _role(role_id, name):
    return SimpleNamespace(id=role_id, name=name)


def test_user_create_requires_at_least_one_role():
    with pytest.raises(ValidationError):
        UserCreate(username="alice", password="password123", role_ids=[])


def test_user_create_accepts_and_deduplicates_role_ids():
    user = UserCreate(username="alice", password="password123", role_ids=[1, 2, 1])

    assert user.role_ids == [1, 2]


def test_user_model_declares_nullable_unique_indexed_email():
    column = User.__table__.c.user_email_address

    assert column.nullable is True
    assert column.unique is True
    assert column.index is True


def test_user_create_email_is_optional_and_normalized():
    without_email = UserCreate(username="alice", password="password123", role_ids=[2])
    with_email = UserCreate(
        username="bob",
        password="password123",
        role_ids=[2],
        user_email_address="  Bob.Student@Example.COM ",
    )

    assert without_email.user_email_address is None
    assert with_email.user_email_address == "bob.student@example.com"


def test_user_create_rejects_malformed_email():
    with pytest.raises(ValidationError):
        UserCreate(
            username="alice",
            password="password123",
            role_ids=[2],
            user_email_address="not-an-email",
        )


def test_user_update_accepts_password_and_role_ids():
    user = UserUpdate(password="password123", role_ids=[3, 3])

    assert user.password == "password123"
    assert user.role_ids == [3]


def test_user_update_email_accepts_null_and_normalizes_a_value():
    cleared = UserUpdate(user_email_address=None)
    updated = UserUpdate(user_email_address="  Alice@Example.COM ")

    assert cleared.user_email_address is None
    assert "user_email_address" in cleared.model_fields_set
    assert updated.user_email_address == "alice@example.com"


def test_user_read_projection_includes_email():
    from app.web.routes.users_route import to_user_read

    user = SimpleNamespace(
        id=7,
        username="alice",
        user_email_address="alice@example.com",
        roles=[SimpleNamespace(id=2, name="student")],
    )

    result = to_user_read(user)

    assert result.user_email_address == "alice@example.com"


def test_get_me_response_includes_null_email(
    api_client,
    override_current_user,
):
    override_current_user(
        username="alice",
        roles=["student"],
        user_email_address=None,
    )

    response = api_client.get("/users/me")

    assert response.status_code == 200
    assert "user_email_address" in response.json()
    assert response.json()["user_email_address"] is None


def test_register_duplicate_email_returns_bad_request(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    async def duplicate_email(*_args, **_kwargs):
        raise ValueError("Email address already exists")

    override_current_user(username="admin", roles=["admin"])
    override_session()
    allow_roles("admin")
    monkeypatch.setattr(users_service, "create_user_service", duplicate_email)

    response = api_client.post(
        "/users/register",
        json={
            "username": "alice",
            "password": "password123",
            "role_ids": [2],
            "user_email_address": "alice@example.com",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email address already exists"


@pytest.mark.asyncio
async def test_user_repo_create_persists_normalized_email(monkeypatch):
    class Session:
        def __init__(self):
            self.added = []

        def add(self, value):
            self.added.append(value)

        async def exec(self, _statement):
            return SimpleNamespace(first=lambda: None)

        async def flush(self):
            self.added[0].id = 10

        async def commit(self):
            return None

        async def rollback(self):
            return None

    session = Session()

    async def fake_ensure_username_available(*_args, **_kwargs):
        return None

    async def fake_ensure_roles_exist(*_args, **_kwargs):
        return None

    async def fake_get_user_by_id(*_args, **_kwargs):
        return session.added[0]

    monkeypatch.setattr(users_repo, "ensure_username_available", fake_ensure_username_available)
    monkeypatch.setattr(users_repo, "ensure_roles_exist", fake_ensure_roles_exist)
    monkeypatch.setattr(users_repo, "get_user_by_id", fake_get_user_by_id)

    created = await users_repo.create_user(
        UserCreate(
            username="alice",
            password="password123",
            role_ids=[2],
            user_email_address="Alice@Example.COM",
        ),
        session,
    )

    assert created.user_email_address == "alice@example.com"


@pytest.mark.asyncio
async def test_user_repo_create_rejects_duplicate_email(monkeypatch):
    existing = User(
        id=9,
        username="existing",
        user_email_address="alice@example.com",
        hashed_password="hashed",
    )

    class Session:
        async def exec(self, _statement):
            return SimpleNamespace(first=lambda: existing)

        def add(self, _value):
            raise AssertionError("duplicate email must be rejected before persistence")

        async def rollback(self):
            return None

    async def fake_ensure_username_available(*_args, **_kwargs):
        return None

    async def fake_ensure_roles_exist(*_args, **_kwargs):
        return None

    monkeypatch.setattr(users_repo, "ensure_username_available", fake_ensure_username_available)
    monkeypatch.setattr(users_repo, "ensure_roles_exist", fake_ensure_roles_exist)

    with pytest.raises(ValueError, match="Email address already exists"):
        await users_repo.create_user(
            UserCreate(
                username="alice",
                password="password123",
                role_ids=[2],
                user_email_address="ALICE@example.com",
            ),
            Session(),
        )


@pytest.mark.asyncio
async def test_user_repo_create_translates_email_integrity_error(monkeypatch):
    class Session:
        def __init__(self):
            self.rollback_calls = 0

        def add(self, _value):
            return None

        async def flush(self):
            raise IntegrityError(
                "INSERT INTO user",
                {},
                Exception("UNIQUE constraint failed: user.user_email_address"),
            )

        async def rollback(self):
            self.rollback_calls += 1

    session = Session()

    async def available(*_args, **_kwargs):
        return None

    monkeypatch.setattr(users_repo, "ensure_username_available", available)
    monkeypatch.setattr(users_repo, "ensure_user_email_address_available", available)
    monkeypatch.setattr(users_repo, "ensure_roles_exist", available)

    with pytest.raises(ValueError, match="Email address already exists"):
        await users_repo.create_user(
            UserCreate(
                username="alice",
                password="password123",
                role_ids=[2],
                user_email_address="alice@example.com",
            ),
            session,
        )

    assert session.rollback_calls == 1


@pytest.mark.asyncio
async def test_email_availability_allows_current_users_address(monkeypatch):
    current_user = User(
        id=10,
        username="alice",
        user_email_address="alice@example.com",
        hashed_password="hashed",
    )

    async def fake_get_user_by_email_address(*_args, **_kwargs):
        return current_user

    monkeypatch.setattr(
        users_repo,
        "get_user_by_email_address",
        fake_get_user_by_email_address,
    )

    await users_repo.ensure_user_email_address_available(
        "alice@example.com",
        object(),
        exclude_user_id=10,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("new_email", ["new@example.com", None])
async def test_user_repo_update_replaces_or_clears_email(monkeypatch, new_email):
    user = User(
        id=10,
        username="alice",
        user_email_address="old@example.com",
        hashed_password="hashed",
    )

    class Session:
        async def exec(self, _statement):
            return SimpleNamespace(first=lambda: None)

    async def fake_commit_and_refresh(_session, updated_user):
        return updated_user

    monkeypatch.setattr(users_repo, "commit_and_refresh", fake_commit_and_refresh)

    result = await users_repo.update_user(
        user,
        UserUpdate(user_email_address=new_email),
        Session(),
    )

    assert result.user_email_address == new_email


@pytest.mark.asyncio
async def test_user_repo_update_translates_email_integrity_error(monkeypatch):
    user = User(
        id=10,
        username="alice",
        user_email_address="old@example.com",
        hashed_password="hashed",
    )

    async def available(*_args, **_kwargs):
        return None

    async def fail_commit(*_args, **_kwargs):
        raise IntegrityError(
            "UPDATE user",
            {},
            Exception("duplicate key: user_email_address"),
        )

    monkeypatch.setattr(users_repo, "ensure_user_email_address_available", available)
    monkeypatch.setattr(users_repo, "commit_and_refresh", fail_commit)

    with pytest.raises(ValueError, match="Email address already exists"):
        await users_repo.update_user(
            user,
            UserUpdate(user_email_address="new@example.com"),
            object(),
        )


@pytest.mark.asyncio
async def test_admin_create_user_with_multiple_roles(monkeypatch, fake_user_factory):
    captured = []

    async def fake_create_user(user_data, session):
        captured.append(user_data)
        return fake_user_factory(user_id=10, roles=("student", "teacher"))

    monkeypatch.setattr(users_service.users_repo, "create_user", fake_create_user)

    user_data = UserCreate(username="alice", password="password123", role_ids=[2, 3])
    user = await users_service.create_user_service(user_data, object(), fake_user_factory(roles="admin"))

    assert user.id == 10
    assert captured == [user_data]


@pytest.mark.asyncio
async def test_non_admin_create_update_delete_denied(fake_user_factory):
    user_data = UserCreate(username="alice", password="password123", role_ids=[2])
    student = fake_user_factory(user_id=2, roles="student")

    with pytest.raises(PermissionError, match="Admin role required"):
        await users_service.create_user_service(user_data, object(), student)

    with pytest.raises(PermissionError, match="Admin role required"):
        await users_service.update_user_service(10, UserUpdate(username="bob"), object(), student)

    with pytest.raises(PermissionError, match="Admin role required"):
        await users_service.delete_user_service(10, object(), student)


@pytest.mark.asyncio
async def test_admin_update_user_username_password_and_roles(monkeypatch, fake_user_factory):
    target = fake_user_factory(user_id=10, roles="student")
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
        fake_user_factory(roles="admin"),
    )

    assert result.username == "bob"
    assert captured_update[0].model_dump(exclude_unset=True) == {
        "username": "bob",
        "password": "password123",
    }
    assert captured_roles == [[2, 3]]


@pytest.mark.asyncio
async def test_owner_password_change_requires_current_password(monkeypatch, fake_user_factory):
    async def fake_update_user(user, user_data, session):
        user.hashed_password = user_data.password
        return user

    monkeypatch.setattr(users_service, "verify_password", lambda raw, hashed: raw == "old-password")
    monkeypatch.setattr(users_service.users_repo, "update_user", fake_update_user)

    current_user = fake_user_factory(
        user_id=2,
        roles=(),
        hashed_password="hashed",
    )
    current_user.roles = [_role(2, "student")]
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
async def test_delete_propagates_repo_deletion_guards(monkeypatch, fake_user_factory):
    async def fake_get_user_by_id(user_id, session):
        return fake_user_factory(user_id=user_id)

    async def fake_delete_user(user, session, current_admin_id=None):
        raise ValueError("Admins cannot delete their own user account")

    monkeypatch.setattr(users_service.users_repo, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(users_service.users_repo, "delete_user", fake_delete_user)

    with pytest.raises(ValueError, match="Admins cannot delete their own user account"):
        await users_service.delete_user_service(1, object(), fake_user_factory(user_id=1, roles="admin"))


@pytest.mark.asyncio
async def test_login_creates_session_and_returns_token_metadata(monkeypatch, fake_user_factory):
    expires_at = object()
    created_session = SimpleNamespace(id=42, expires_at=expires_at)

    async def fake_get_user_by_username(username, session):
        assert username == "alice"
        return fake_user_factory(user_id=7, roles=(), hashed_password="hashed")

    async def fake_create_login_session(user, session):
        assert user.id == 7
        return created_session

    monkeypatch.setattr(users_service.users_repo, "get_user_by_username", fake_get_user_by_username)
    monkeypatch.setattr(users_service, "verify_password", lambda raw, hashed: raw == "secret")
    monkeypatch.setattr(users_service.sessions_service, "create_login_session_srvc", fake_create_login_session)
    monkeypatch.setattr(
        users_service,
        "create_access_token",
        lambda username, session_id=None: f"token-{username}-{session_id}",
    )

    access_token, token_type, session_id, token_expires_at = await users_service.user_login_service(
        "alice",
        "secret",
        object(),
    )

    assert access_token == "token-alice-42"
    assert token_type == "bearer"
    assert session_id == 42
    assert token_expires_at is expires_at


@pytest.mark.asyncio
async def test_admin_can_list_roles(monkeypatch, fake_user_factory):
    roles = [_role(1, "admin"), _role(2, "student"), _role(3, "teacher")]

    async def fake_list_roles(session):
        return roles

    monkeypatch.setattr(users_service.users_repo, "list_roles", fake_list_roles)

    result = await users_service.list_roles_service(object(), fake_user_factory(roles="admin"))

    assert result == roles


@pytest.mark.asyncio
async def test_non_admin_role_listing_denied(fake_user_factory):
    with pytest.raises(PermissionError, match="Admin role required"):
        await users_service.list_roles_service(object(), fake_user_factory(user_id=2, roles="student"))


def test_users_router_is_mounted_and_static_routes_precede_username_route(test_app: FastAPI):
    paths = [route.path for route in test_app.routes]

    assert "/users/login" in paths
    assert "/users/register" in paths
    assert "/users/roles" in paths
    assert "/users/me/password" in paths
    assert paths.index("/users/me") < paths.index("/users/{username}")
    assert paths.index("/users/roles") < paths.index("/users/{username}")
    assert "/scenarios/" in paths
    assert "/scenarios/{scenario_id}" in paths
    assert "/scenarios/{scenario_id}/copy" in paths
    assert "/simulations/" in paths
    assert "/simulations/{simulation_id}" in paths
    assert "/simulations/{simulation_id}/turn" in paths
    assert "/simulations/{simulation_id}/review" in paths
    assert "/sessions/" in paths
    assert "/sessions/{session_id}" in paths
    assert "/sessions/{session_id}/heartbeat" in paths
    assert "/sessions/{session_id}/end" in paths
    assert "/prompts/" in paths
    assert "/prompts/{prompt_id}" in paths
    assert "/prompts/{prompt_id}/copy" in paths
    assert "/vector-stores/" in paths
    assert "/vector-stores/{vector_store_id}" in paths
    assert "/vector-stores/{vector_store_id}/connection" in paths
    assert "/chunking-profiles/" in paths
    assert "/chunking-profiles/{profile_id}" in paths
    assert "/chunking-profiles/{profile_id}/copy" in paths
    assert "/corpora/{corpus_id}/chunking-profiles/{profile_id}/vector-stores/{vector_store_id}/embed-jobs" in paths
    assert "/corpus-indices/" in paths
    assert "/corpus-indices/{index_id}" in paths
    assert "/corpus-indices/{index_id}/indexed-chunks" in paths
    assert "/corpus-indices/{index_id}/status" in paths
    assert "/corpus-indices/{index_id}/build-complete" in paths
    assert "/corpus-indices/{index_id}/copy" in paths
