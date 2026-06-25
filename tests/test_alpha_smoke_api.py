from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.core import dependencies
from app.schemas.corpus_schemas import CorpusRead
from app.schemas.embeddings_schemas import CorpusEmbeddingBuildQueued
from app.schemas.raw_documents_schemas import RawDocumentRead
from app.schemas.simulations_schemas import (
    NegotiationStateSchema,
    SimulationProxyDisableResponse,
    SimulationProxyTurnResponse,
    SimulationMessageSchema,
    SimulationRead,
    SimulationReadWithState,
    SimulationTurnResponse,
)
from app.schemas.simulation_learner_schemas import SimulationLearnerAskResponse


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:3000"])
def test_alpha_smoke_login_upload_corpus_index_and_simulation_turn(monkeypatch, origin):
    async def fake_startup_seed():
        return None

    async def fake_get_current_user():
        return SimpleNamespace(id=1, username="admin", roles=[SimpleNamespace(name="admin")])

    async def fake_get_session():
        yield object()

    async def fake_user_has_role(_user, _role_name, _session):
        return True

    async def fake_login(username, password, session):
        assert username == "admin"
        assert password == "secret"
        return "alpha-token", "bearer", 44, _now()

    async def fake_create_uploaded_raw_document(**kwargs):
        assert kwargs["name"] == "alpha brief"
        assert kwargs["upload"].filename == "brief.pdf"
        return RawDocumentRead(
            id=21,
            name="alpha brief",
            description="Uploaded for smoke testing",
            source_path="app/raw_docs_store/alpha-brief.pdf",
            source_hash="abc123",
            source_size=2048,
            source_mtime=_now(),
            source_status="available",
            uploaded_at=_now(),
            uploaded_by_user_id=1,
            parsed_at=None,
        )

    async def fake_create_corpus(corpus_data, session, current_user):
        assert corpus_data.raw_document_ids == [21]
        assert current_user.id == 1
        return CorpusRead(
            id=11,
            name=corpus_data.name,
            description=corpus_data.description,
            created_by_user_id=1,
            created_by_username="admin",
            last_edit_by_user_id=None,
            last_edit_by_username=None,
            created_at=_now(),
        )

    async def fake_queue_embed_job(**kwargs):
        assert kwargs["corpus"].id == 11
        assert kwargs["chunking_profile"].id == 3
        assert kwargs["vector_store"].id == 5
        return CorpusEmbeddingBuildQueued(
            corpus_id=11,
            corpus_index_id=77,
            vector_store_id=5,
            chunking_profile_id=3,
            embedding_model="mini-l6-v2",
            embedding_dimensions=384,
            vector_namespace="corpus-index-77",
            status="building",
        )

    async def fake_run_embed_job(_corpus_index_id):
        return None

    async def fake_create_simulation(simulation_data, session, current_user):
        assert current_user.id == 1
        return SimulationRead(
            id=31,
            name=simulation_data.name,
            description=simulation_data.description,
            status="created",
            session_id=None,
            user_id_owner=1,
            user_id_participant=None,
            scenario_id=None,
            corpus_id=simulation_data.corpus_id,
            corpus_index_id=simulation_data.corpus_index_id,
            coach_prompt_id=None,
            counterpart_prompt_id=None,
            evaluator_prompt_id=None,
            rag_profile_id=simulation_data.rag_profile_id,
            counter_part_side_persona_id=None,
            user_side=simulation_data.user_side,
            teacher_reviewed=False,
            teacher_id=None,
            teacher_feedback=None,
            reviewed_at=None,
            created_at=_now(),
            last_updated=_now(),
        )

    simulation_record = SimpleNamespace(
        id=31,
        status="created",
        user_id_owner=1,
        user_id_participant=None,
        teacher_id=None,
        rag_profile_id=500,
        user_side="side_a",
    )

    async def fake_get_accessible_simulation():
        return simulation_record

    async def fake_start_simulation(simulation, start_data, session, current_user):
        simulation.status = "active"
        assert simulation.id == 31
        return SimulationReadWithState(
            id=31,
            name="alpha simulation",
            description="Smoke-test simulation",
            status="active",
            session_id=None,
            user_id_owner=1,
            user_id_participant=None,
            scenario_id=None,
            corpus_id=11,
            corpus_index_id=77,
            rag_profile_id=500,
            coach_prompt_id=None,
            counterpart_prompt_id=None,
            evaluator_prompt_id=None,
            counter_part_side_persona_id=None,
            user_side="side_a",
            teacher_reviewed=False,
            teacher_id=None,
            teacher_feedback=None,
            reviewed_at=None,
            created_at=_now(),
            last_updated=_now(),
            negotiation_state=NegotiationStateSchema(
                current_phase="opening",
                user_side="side_a",
                data={"simulation_id": "31", "phase": "opening"},
            ),
            messages=[],
        )

    async def fake_submit_turn(simulation, turn_data, session, current_user):
        assert simulation.id == 31
        assert turn_data.message == "Could you do 95?"
        return SimulationTurnResponse(
            simulation_id=31,
            status="paused",
            phase="bargaining",
            should_pause=True,
            pause_reason="counterpart_response_ready",
            messages=[
                SimulationMessageSchema(role="user", content="Could you do 95?"),
                SimulationMessageSchema(
                    role="assistant",
                    content="I can move a little, but not that far.",
                ),
            ],
            coach_advice={"summary": "Hold near target."},
            counterpart_response="I can move a little, but not that far.",
        )

    monkeypatch.setattr(main_module, "startup_seed", fake_startup_seed)
    monkeypatch.setattr(dependencies, "user_has_role", fake_user_has_role)

    from app.services import simulations_service, users_service
    from app.web.routes import corpus_route, raw_documents_route

    monkeypatch.setattr(users_service, "user_login_service", fake_login)
    monkeypatch.setattr(
        raw_documents_route,
        "create_uploaded_raw_document_srvc",
        fake_create_uploaded_raw_document,
    )
    monkeypatch.setattr(corpus_route, "create_corpus_srvc", fake_create_corpus)
    monkeypatch.setattr(
        corpus_route,
        "queue_corpus_embedding_build_srvc",
        fake_queue_embed_job,
    )
    monkeypatch.setattr(
        corpus_route,
        "run_queued_corpus_embedding_build_srvc",
        fake_run_embed_job,
    )
    monkeypatch.setattr(
        simulations_service,
        "create_simulation_srvc",
        fake_create_simulation,
    )
    monkeypatch.setattr(
        simulations_service,
        "start_simulation_srvc",
        fake_start_simulation,
    )
    monkeypatch.setattr(
        simulations_service,
        "submit_simulation_turn_srvc",
        fake_submit_turn,
    )

    app = main_module.app
    app.dependency_overrides[dependencies.get_current_user] = fake_get_current_user
    app.dependency_overrides[dependencies.get_session] = fake_get_session
    app.dependency_overrides[dependencies.get_corpus_or_404] = (
        lambda: SimpleNamespace(id=11, created_by_user_id=1)
    )
    app.dependency_overrides[dependencies.get_chunking_profile_or_404] = (
        lambda: SimpleNamespace(id=3)
    )
    app.dependency_overrides[dependencies.get_vector_store_record_or_404] = (
        lambda: SimpleNamespace(id=5)
    )
    app.dependency_overrides[dependencies.get_accessible_simulation] = fake_get_accessible_simulation

    try:
        with TestClient(app) as client:
            preflight = client.options(
                "/raw-documents/",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                },
            )
            assert preflight.status_code == 200
            assert preflight.headers["access-control-allow-origin"] == origin

            login_response = client.post(
                "/users/login",
                data={"username": "admin", "password": "secret"},
            )
            assert login_response.status_code == 200
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}", "Origin": origin}

            upload_response = client.post(
                "/raw-documents/",
                data={
                    "name": "alpha brief",
                    "description": "Uploaded for smoke testing",
                },
                files={"file": ("brief.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
                headers=headers,
            )
            assert upload_response.status_code == 201
            assert upload_response.json()["id"] == 21
            assert upload_response.json()["uploaded_by_username"] == "admin"

            corpus_response = client.post(
                "/corpora/",
                json={
                    "name": "alpha corpus",
                    "description": "Corpus for alpha smoke test",
                    "raw_document_ids": [21],
                },
                headers=headers,
            )
            assert corpus_response.status_code == 201
            assert corpus_response.json()["id"] == 11
            assert corpus_response.json()["created_by_username"] == "admin"

            index_response = client.post(
                "/corpora/11/chunking-profiles/3/vector-stores/5/embed-jobs",
                json={
                    "name": "alpha index",
                    "embedding_model": "mini-l6-v2",
                },
                headers=headers,
            )
            assert index_response.status_code == 202
            assert index_response.json()["corpus_index_id"] == 77

            simulation_response = client.post(
                "/simulations/",
                json={
                    "name": "alpha simulation",
                    "description": "Smoke-test simulation",
                    "corpus_id": 11,
                    "corpus_index_id": 77,
                    "rag_profile_id": 500,
                    "user_side": "side_a",
                },
                headers=headers,
            )
            assert simulation_response.status_code == 201
            assert simulation_response.json()["id"] == 31

            start_response = client.post(
                "/simulations/31/start",
                json={
                    "side_a": {"name": "Buyer", "role": "buyer"},
                    "side_b": {"name": "Seller", "role": "seller"},
                },
                headers=headers,
            )
            assert start_response.status_code == 200
            assert start_response.json()["status"] == "active"

            turn_response = client.post(
                "/simulations/31/turn",
                json={"message": "Could you do 95?"},
                headers=headers,
            )
            assert turn_response.status_code == 200
            assert turn_response.json()["status"] == "paused"
            assert turn_response.json()["counterpart_response"] == (
                "I can move a little, but not that far."
            )
    finally:
        app.dependency_overrides.clear()


def test_alpha_smoke_proxy_turn_and_disable_routes(monkeypatch):
    async def fake_startup_seed():
        return None

    async def fake_get_current_user():
        return SimpleNamespace(id=1, username="student", roles=[])

    async def fake_get_session():
        yield object()

    simulation_record = SimpleNamespace(
        id=31,
        status="paused",
        user_id_owner=1,
        user_id_participant=None,
        teacher_id=None,
        user_side="side_a",
    )

    async def fake_get_accessible_simulation():
        return simulation_record

    async def fake_proxy_turn(simulation, proxy_data, session, current_user):
        assert simulation.id == 31
        assert proxy_data.duration == "this_turn"
        assert proxy_data.persona_id is None
        assert current_user.id == 1
        return SimulationProxyTurnResponse(
            simulation_id=31,
            status="paused",
            phase="bargaining",
            should_pause=True,
            pause_reason="counterpart_response_ready",
            messages=[
                SimulationMessageSchema(
                    role="user",
                    content="I can move to 100 if we can settle today.",
                    metadata={"user_reply_origin": "auto_user_proxy"},
                )
            ],
            coach_advice={},
            final_evaluation={},
            counterpart_response="I can do 98.",
            proxy_response="I can move to 100 if we can settle today.",
            auto_user_proxy_enabled=False,
            user_proxy_persona={},
        )

    async def fake_disable_proxy(simulation, session, current_user):
        assert simulation.id == 31
        assert current_user.id == 1
        return SimulationProxyDisableResponse(
            simulation_id=31,
            status="paused",
            auto_user_proxy_enabled=False,
            user_proxy_persona={},
            messages=[],
        )

    monkeypatch.setattr(main_module, "startup_seed", fake_startup_seed)

    from app.services import simulations_service

    monkeypatch.setattr(
        simulations_service,
        "submit_simulation_proxy_turn_srvc",
        fake_proxy_turn,
    )
    monkeypatch.setattr(
        simulations_service,
        "disable_simulation_proxy_srvc",
        fake_disable_proxy,
    )

    app = main_module.app
    app.dependency_overrides[dependencies.get_current_user] = fake_get_current_user
    app.dependency_overrides[dependencies.get_session] = fake_get_session
    app.dependency_overrides[dependencies.get_accessible_simulation] = fake_get_accessible_simulation

    try:
        with TestClient(app) as client:
            proxy_turn_response = client.post(
                "/simulations/31/proxy-turn",
                json={"persona_id": None, "duration": "this_turn"},
            )
            assert proxy_turn_response.status_code == 200
            assert proxy_turn_response.json()["proxy_response"] == (
                "I can move to 100 if we can settle today."
            )

            disable_response = client.post("/simulations/31/proxy/disable", json={})
            assert disable_response.status_code == 200
            assert disable_response.json()["auto_user_proxy_enabled"] is False
    finally:
        app.dependency_overrides.clear()


def test_alpha_smoke_learner_ask_route(monkeypatch):
    async def fake_startup_seed():
        return None

    async def fake_get_current_user():
        return SimpleNamespace(id=1, username="student", roles=[])

    async def fake_get_session():
        yield object()

    simulation_record = SimpleNamespace(
        id=31,
        status="paused",
        user_id_owner=1,
        user_id_participant=None,
        teacher_id=None,
        user_side="side_a",
    )

    async def fake_get_accessible_simulation():
        return simulation_record

    async def fake_learner_ask(simulation, ask_data, session, current_user):
        assert simulation.id == 31
        assert ask_data.query == "What should I focus on?"
        assert ask_data.max_results == 2
        assert current_user.id == 1
        return SimulationLearnerAskResponse(
            simulation_id=31,
            status="paused",
            answer="Focus on objective criteria.",
            metadata={"tools_available": ["crag_tool"]},
        )

    monkeypatch.setattr(main_module, "startup_seed", fake_startup_seed)

    from app.services import simulation_learner_service

    monkeypatch.setattr(
        simulation_learner_service,
        "ask_simulation_learner_srvc",
        fake_learner_ask,
    )

    app = main_module.app
    app.dependency_overrides[dependencies.get_current_user] = fake_get_current_user
    app.dependency_overrides[dependencies.get_session] = fake_get_session
    app.dependency_overrides[dependencies.get_accessible_simulation] = fake_get_accessible_simulation

    try:
        with TestClient(app) as client:
            response = client.post(
                "/simulations/31/learner/ask",
                json={"query": "What should I focus on?", "max_results": 2},
            )

            assert response.status_code == 200
            assert response.json()["answer"] == "Focus on objective criteria."
            assert response.json()["metadata"]["tools_available"] == ["crag_tool"]
    finally:
        app.dependency_overrides.clear()


def test_raw_document_detail_returns_uploader_username(monkeypatch):
    async def fake_startup_seed():
        return None

    async def fake_get_session():
        yield object()

    async def fake_get_raw_document_by_id_srvc(_session, raw_document_id):
        assert raw_document_id == 21
        return SimpleNamespace(
            id=21,
            name="alpha brief",
            description="Uploaded for smoke testing",
            source_path="app/raw_docs_store/alpha-brief.pdf",
            source_hash="abc123",
            source_size=2048,
            source_mtime=_now(),
            source_status="available",
            uploaded_at=_now(),
            uploaded_by_user_id=1,
            uploaded_by=SimpleNamespace(username="teacher"),
            parsed_at=None,
        )

    monkeypatch.setattr(main_module, "startup_seed", fake_startup_seed)

    from app.web.routes import raw_documents_route

    monkeypatch.setattr(
        raw_documents_route,
        "get_raw_document_by_id_srvc",
        fake_get_raw_document_by_id_srvc,
    )

    app = main_module.app
    app.dependency_overrides[dependencies.get_session] = fake_get_session

    try:
        with TestClient(app) as client:
            response = client.get("/raw-documents/21")

        assert response.status_code == 200
        assert response.json()["uploaded_by_user_id"] == 1
        assert response.json()["uploaded_by_username"] == "teacher"
    finally:
        app.dependency_overrides.clear()


def test_list_corpora_returns_creator_and_editor_usernames(monkeypatch):
    async def fake_startup_seed():
        return None

    async def fake_get_session():
        yield object()

    async def fake_list_corpora_srvc(*_args, **_kwargs):
        return [
            SimpleNamespace(
                id=11,
                name="alpha corpus",
                description="Corpus for smoke testing",
                created_by_user_id=1,
                created_by_user=SimpleNamespace(username="teacher"),
                last_edit_by_user_id=2,
                last_edit_by_user=SimpleNamespace(username="coach"),
                created_at=_now(),
            )
        ]

    monkeypatch.setattr(main_module, "startup_seed", fake_startup_seed)

    from app.web.routes import corpus_route

    monkeypatch.setattr(corpus_route, "list_corpora_srvc", fake_list_corpora_srvc)

    app = main_module.app
    app.dependency_overrides[dependencies.get_session] = fake_get_session

    try:
        with TestClient(app) as client:
            response = client.get("/corpora/")

        assert response.status_code == 200
        assert response.json()[0]["created_by_username"] == "teacher"
        assert response.json()[0]["last_edit_by_username"] == "coach"
    finally:
        app.dependency_overrides.clear()
