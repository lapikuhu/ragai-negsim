from types import SimpleNamespace

import pytest

import scripts.seeder as seeder


class FakeSession:
    def __init__(self):
        self.rollback_calls = 0

    async def rollback(self):
        self.rollback_calls += 1


def _admin_user():
    return SimpleNamespace(id=1, username="admin", roles=[SimpleNamespace(name="admin")])


def _role(role_id: int, name: str):
    return SimpleNamespace(id=role_id, name=name)


def _scenario_names():
    return [item["name"] for item in seeder.PLACEHOLDER_SCENARIOS]


def _persona_names():
    return [item["name"] for item in seeder.PLACEHOLDER_PERSONAS]


@pytest.mark.asyncio
async def test_ensure_admin_user_uses_settings_username(monkeypatch):
    calls = []
    admin_user = _admin_user()

    async def fake_seed_roles():
        calls.append("roles")

    async def fake_create_admin():
        calls.append("admin")

    async def fake_get_user_by_username(username, session):
        calls.append(("lookup", username, session))
        return admin_user

    monkeypatch.setattr(seeder, "seed_roles_if_not_exist", fake_seed_roles)
    monkeypatch.setattr(seeder, "create_admin_if_not_exists", fake_create_admin)
    monkeypatch.setattr(seeder.users_repo, "get_user_by_username", fake_get_user_by_username)

    session = FakeSession()
    result = await seeder.ensure_admin_user(session)

    assert result is admin_user
    assert calls == [
        "roles",
        "admin",
        ("lookup", seeder.settings.ADMIN_USERNAME, session),
    ]


@pytest.mark.asyncio
async def test_ensure_admin_user_logs_success(monkeypatch, capsys):
    admin_user = _admin_user()

    async def fake_seed_roles():
        return None

    async def fake_create_admin():
        return None

    async def fake_get_user_by_username(username, session):
        return admin_user

    monkeypatch.setattr(seeder, "seed_roles_if_not_exist", fake_seed_roles)
    monkeypatch.setattr(seeder, "create_admin_if_not_exists", fake_create_admin)
    monkeypatch.setattr(seeder.users_repo, "get_user_by_username", fake_get_user_by_username)

    session = FakeSession()
    result = await seeder.ensure_admin_user(session)

    captured = capsys.readouterr()

    assert result is admin_user
    assert "[ready] admin user admin" in captured.out


@pytest.mark.asyncio
async def test_seed_all_creates_requested_records(monkeypatch):
    admin_user = _admin_user()
    session = FakeSession()
    created_users = []
    created_scenarios = []
    created_personas = []
    created_profiles = []
    created_stores = []
    model_calls = []

    async def fake_ensure_admin_user(current_session):
        assert current_session is session
        return admin_user

    async def fake_get_user_by_username(username, current_session):
        return None

    async def fake_get_role_by_name(role_name, current_session):
        return {
            "student": _role(2, "student"),
            "teacher": _role(3, "teacher"),
        }[role_name]

    async def fake_create_user_service(user_data, current_session, current_user):
        created_users.append((user_data, current_user))
        return SimpleNamespace(id=len(created_users) + 10, username=user_data.username)

    async def fake_get_scenario_by_name(name, current_session):
        return None

    def fake_get_chat_model(provider="openai", model_name="gpt-4o-mini", temperature=0.0):
        model_calls.append((provider, model_name, temperature))
        return SimpleNamespace(name="fake-model")

    async def fake_generate_scenario_context_srvc(scenario_data, model):
        return SimpleNamespace(
            public_context={"name": scenario_data.name, "description": scenario_data.description},
            side_a_private_context={"side": "A", "scenario": scenario_data.name},
            side_b_private_context={"side": "B", "scenario": scenario_data.name},
        )

    async def fake_create_scenario_srvc(scenario_data, current_session, current_user):
        created_scenarios.append((scenario_data, current_user))
        return SimpleNamespace(id=len(created_scenarios))

    async def fake_get_counterpart_persona_by_name(name, current_session):
        return None

    async def fake_create_counterpart_persona_srvc(persona_data, current_session, current_user):
        created_personas.append((persona_data, current_user))
        return SimpleNamespace(id=len(created_personas))

    async def fake_get_chunking_profile_by_name(name, current_session):
        return None

    async def fake_create_chunking_profile_srvc(profile_data, current_session):
        created_profiles.append(profile_data)
        return SimpleNamespace(id=len(created_profiles))

    async def fake_get_vector_store_by_name(name, current_session):
        return None

    async def fake_create_vector_store_srvc(store_data, current_session):
        created_stores.append(store_data)
        return SimpleNamespace(id=len(created_stores))

    monkeypatch.setattr(seeder, "ensure_admin_user", fake_ensure_admin_user)
    monkeypatch.setattr(seeder.users_repo, "get_user_by_username", fake_get_user_by_username)
    monkeypatch.setattr(seeder.users_repo, "get_role_by_name", fake_get_role_by_name)
    monkeypatch.setattr(seeder.users_service, "create_user_service", fake_create_user_service)
    monkeypatch.setattr(seeder.scenarios_repo, "get_scenario_by_name", fake_get_scenario_by_name)
    monkeypatch.setattr(seeder, "get_chat_model", fake_get_chat_model)
    monkeypatch.setattr(
        seeder.scenarios_service,
        "generate_scenario_context_srvc",
        fake_generate_scenario_context_srvc,
    )
    monkeypatch.setattr(seeder.scenarios_service, "create_scenario_srvc", fake_create_scenario_srvc)
    monkeypatch.setattr(
        seeder.counterpart_personas_repo,
        "get_counterpart_persona_by_name",
        fake_get_counterpart_persona_by_name,
    )
    monkeypatch.setattr(
        seeder.counterpart_personas_service,
        "create_counterpart_persona_srvc",
        fake_create_counterpart_persona_srvc,
    )
    monkeypatch.setattr(
        seeder.chunking_profiles_repo,
        "get_chunking_profile_by_name",
        fake_get_chunking_profile_by_name,
    )
    monkeypatch.setattr(
        seeder.chunking_profiles_service,
        "create_chunking_profile_srvc",
        fake_create_chunking_profile_srvc,
    )
    monkeypatch.setattr(seeder.vector_stores_repo, "get_vector_store_by_name", fake_get_vector_store_by_name)
    monkeypatch.setattr(seeder.vector_stores_service, "create_vector_store_srvc", fake_create_vector_store_srvc)

    await seeder.seed_all(session)

    assert [payload.username for payload, _ in created_users] == ["student1", "teacher1"]
    assert [payload.role_ids for payload, _ in created_users] == [[2], [3]]
    assert all(current_user is admin_user for _, current_user in created_users)

    assert [payload.name for payload, _ in created_scenarios] == _scenario_names()
    assert created_scenarios[0][0].public_context == {
        "name": seeder.PLACEHOLDER_SCENARIOS[0]["name"],
        "description": seeder.PLACEHOLDER_SCENARIOS[0]["description"],
    }
    assert created_scenarios[0][0].side_a_private_context == {
        "side": "A",
        "scenario": seeder.PLACEHOLDER_SCENARIOS[0]["name"],
    }
    assert created_scenarios[0][0].side_b_private_context == {
        "side": "B",
        "scenario": seeder.PLACEHOLDER_SCENARIOS[0]["name"],
    }

    assert [payload.name for payload, _ in created_personas] == _persona_names()
    assert [payload.name for payload in created_profiles] == ["Recursive", "Semantic", "Hybrid"]
    assert [payload.strategy for payload in created_profiles] == ["recursive", "semantic", "hybrid"]
    assert all(payload.config == {} for payload in created_profiles)

    assert [payload.name for payload in created_stores] == [
        "ChromaVectorStoreDim384",
        "FAISSVectorStoreDim768",
        "PGVectorStoreDim1536",
    ]
    assert [payload.embedding_model for payload in created_stores] == [
        "mini-l6-v2",
        "bge-base",
        "text-embedding-3-small",
    ]
    assert created_stores[0].collection_name == "negotiation_collection_384"
    assert created_stores[0].path == "./chroma_db/dim384"
    assert created_stores[1].path == "./faiss_db/dim768"
    assert created_stores[2].table_name == "negotiation_collection_1536"
    assert model_calls == [("openai", "gpt-4o-mini", 0.0)] * 5
    assert session.rollback_calls == 0


@pytest.mark.asyncio
async def test_seed_all_skips_existing_scenario_without_generating_context(monkeypatch):
    admin_user = _admin_user()
    session = FakeSession()
    created_scenarios = []
    generated = []

    async def fake_ensure_admin_user(current_session):
        return admin_user

    async def fake_get_user_by_username(username, current_session):
        return SimpleNamespace(id=50, username=username) if username in {"student1", "teacher1"} else None

    async def fake_get_scenario_by_name(name, current_session):
        if name == seeder.PLACEHOLDER_SCENARIOS[0]["name"]:
            return SimpleNamespace(id=99, name=name)
        return None

    def fake_get_chat_model(provider="openai", model_name="gpt-4o-mini", temperature=0.0):
        return SimpleNamespace(name="fake-model")

    async def fake_generate_scenario_context_srvc(scenario_data, model):
        generated.append(scenario_data.name)
        return SimpleNamespace(
            public_context={},
            side_a_private_context={},
            side_b_private_context={},
        )

    async def fake_create_scenario_srvc(scenario_data, current_session, current_user):
        created_scenarios.append(scenario_data.name)
        return SimpleNamespace(id=len(created_scenarios))

    async def fake_get_counterpart_persona_by_name(name, current_session):
        return SimpleNamespace(id=1, name=name)

    async def fake_get_chunking_profile_by_name(name, current_session):
        return SimpleNamespace(id=1, name=name)

    async def fake_get_vector_store_by_name(name, current_session):
        return SimpleNamespace(id=1, name=name)

    monkeypatch.setattr(seeder, "ensure_admin_user", fake_ensure_admin_user)
    monkeypatch.setattr(seeder.users_repo, "get_user_by_username", fake_get_user_by_username)
    monkeypatch.setattr(seeder.scenarios_repo, "get_scenario_by_name", fake_get_scenario_by_name)
    monkeypatch.setattr(seeder, "get_chat_model", fake_get_chat_model)
    monkeypatch.setattr(
        seeder.scenarios_service,
        "generate_scenario_context_srvc",
        fake_generate_scenario_context_srvc,
    )
    monkeypatch.setattr(seeder.scenarios_service, "create_scenario_srvc", fake_create_scenario_srvc)
    monkeypatch.setattr(
        seeder.counterpart_personas_repo,
        "get_counterpart_persona_by_name",
        fake_get_counterpart_persona_by_name,
    )
    monkeypatch.setattr(seeder.chunking_profiles_repo, "get_chunking_profile_by_name", fake_get_chunking_profile_by_name)
    monkeypatch.setattr(seeder.vector_stores_repo, "get_vector_store_by_name", fake_get_vector_store_by_name)

    await seeder.seed_all(session)

    assert created_scenarios == _scenario_names()[1:]
    assert generated == _scenario_names()[1:]


@pytest.mark.asyncio
async def test_seed_all_rolls_back_and_continues_after_creation_failure(monkeypatch):
    admin_user = _admin_user()
    session = FakeSession()
    created_users = []
    created_personas = []

    async def fake_ensure_admin_user(current_session):
        return admin_user

    async def fake_get_user_by_username(username, current_session):
        return None

    async def fake_get_role_by_name(role_name, current_session):
        return {
            "student": _role(2, "student"),
            "teacher": _role(3, "teacher"),
        }[role_name]

    async def fake_create_user_service(user_data, current_session, current_user):
        if user_data.username == "student1":
            raise RuntimeError("boom")
        created_users.append(user_data.username)
        return SimpleNamespace(id=5, username=user_data.username)

    async def fake_get_scenario_by_name(name, current_session):
        return SimpleNamespace(id=1, name=name)

    async def fake_get_counterpart_persona_by_name(name, current_session):
        return None

    async def fake_create_counterpart_persona_srvc(persona_data, current_session, current_user):
        created_personas.append(persona_data.name)
        return SimpleNamespace(id=8)

    async def fake_get_chunking_profile_by_name(name, current_session):
        return SimpleNamespace(id=1, name=name)

    async def fake_get_vector_store_by_name(name, current_session):
        return SimpleNamespace(id=1, name=name)

    monkeypatch.setattr(seeder, "ensure_admin_user", fake_ensure_admin_user)
    monkeypatch.setattr(seeder.users_repo, "get_user_by_username", fake_get_user_by_username)
    monkeypatch.setattr(seeder.users_repo, "get_role_by_name", fake_get_role_by_name)
    monkeypatch.setattr(seeder.users_service, "create_user_service", fake_create_user_service)
    monkeypatch.setattr(seeder.scenarios_repo, "get_scenario_by_name", fake_get_scenario_by_name)
    monkeypatch.setattr(
        seeder.counterpart_personas_repo,
        "get_counterpart_persona_by_name",
        fake_get_counterpart_persona_by_name,
    )
    monkeypatch.setattr(
        seeder.counterpart_personas_service,
        "create_counterpart_persona_srvc",
        fake_create_counterpart_persona_srvc,
    )
    monkeypatch.setattr(seeder.chunking_profiles_repo, "get_chunking_profile_by_name", fake_get_chunking_profile_by_name)
    monkeypatch.setattr(seeder.vector_stores_repo, "get_vector_store_by_name", fake_get_vector_store_by_name)

    await seeder.seed_all(session)

    assert session.rollback_calls == 1
    assert created_users == ["teacher1"]
    assert created_personas == _persona_names()
