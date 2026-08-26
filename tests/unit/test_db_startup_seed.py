from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_create_admin_uses_configured_email(monkeypatch):
    from app.db import db
    from app.models.user_roles import Role
    from app.models.users import User

    admin_role = Role(id=1, name="admin")

    class Session:
        def __init__(self):
            self.results = [admin_role, None, None]
            self.added = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def exec(self, _statement):
            value = self.results.pop(0)
            return SimpleNamespace(first=lambda: value)

        def add(self, value):
            self.added.append(value)

        async def commit(self):
            return None

    session = Session()
    monkeypatch.setattr(db, "AsyncSessionLocal", lambda: session)

    await db.create_admin_if_not_exists()

    created_admin = next(value for value in session.added if isinstance(value, User))
    assert created_admin.user_email_address == db.settings.ADMIN_EMAIL.lower()


@pytest.mark.asyncio
async def test_create_admin_does_not_overwrite_existing_admin_email(monkeypatch):
    from app.db import db
    from app.models.user_roles import Role
    from app.models.users import User

    admin_role = Role(id=1, name="admin")
    existing_admin = User(
        id=7,
        username=db.settings.ADMIN_USERNAME,
        user_email_address="existing@example.com",
        hashed_password="hashed",
    )

    class Session:
        def __init__(self):
            self.results = [admin_role, existing_admin]
            self.added = []
            self.commit_calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def exec(self, _statement):
            value = self.results.pop(0)
            return SimpleNamespace(first=lambda: value)

        def add(self, value):
            self.added.append(value)

        async def commit(self):
            self.commit_calls += 1

    session = Session()
    monkeypatch.setattr(db, "AsyncSessionLocal", lambda: session)

    await db.create_admin_if_not_exists()

    assert existing_admin.user_email_address == "existing@example.com"
    assert session.added == []
    assert session.commit_calls == 0
