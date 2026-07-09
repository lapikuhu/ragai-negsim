from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any, AsyncGenerator, Callable, Generator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import ASGITransport, AsyncClient
import pytest
import pytest_asyncio


APP_DIR = Path(__file__).resolve().parents[1] / "app"
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


@pytest.fixture(autouse=True)
def disable_langsmith_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Fixture to disable LangSmith tracing for all tests. This prevents 
    any external tracing or logging from interfering with test results.
    """
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGSMITH_TRACING_V2", "false")


@pytest.fixture
def test_app() -> Generator[FastAPI, None, None]:
    """
    Fixture to provide the FastAPI test application.
    """
    from app import main as main_module

    original_lifespan_context = main_module.app.router.lifespan_context

    @asynccontextmanager
    async def noop_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        yield

    main_module.app.router.lifespan_context = noop_lifespan

    try:
        yield main_module.app
    finally:
        main_module.app.dependency_overrides.clear()
        main_module.app.router.lifespan_context = original_lifespan_context


@pytest.fixture
def api_client(test_app: FastAPI) -> Generator[Any, None, None]:
    """
    Fixture to provide the FastAPI sync test client.
    """
    with TestClient(test_app) as client:
        yield client


@pytest_asyncio.fixture
async def async_api_client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Fixture to provide the FastAPI async test client.
    """
    async with AsyncClient(
        base_url="http://testserver",
        transport=ASGITransport(app=test_app),
    ) as client:
        yield client


@pytest.fixture
def fake_user_factory() -> Callable[..., SimpleNamespace]:
    """
    Fixture to create a fake user for testing purposes.
    """
    def create_fake_user(
        user_id: int = 1,
        username: str = "test-user",
        roles: str | list[str] | tuple[str, ...] = ("admin",),
        **attrs: Any,
    ) -> SimpleNamespace:
        role_names = [roles] if isinstance(roles, str) else list(roles)
        user = SimpleNamespace(
            id=user_id,
            username=username,
            roles=[SimpleNamespace(name=role_name) for role_name in role_names],
        )
        for name, value in attrs.items():
            setattr(user, name, value)
        return user

    return create_fake_user


@pytest.fixture
def recording_async_session_factory() -> Callable[[], Any]:
    """
    Fixture to create async session doubles for write-path tests.
    """
    class RecordingAsyncSession:
        def __init__(self) -> None:
            self.added: list[Any] = []
            self.refreshed: list[Any] = []
            self.entered_sessions: list[Any] = []
            self.exited_sessions: list[Any] = []
            self.commit_calls = 0
            self.refresh_calls = 0
            self.rollback_calls = 0

        async def __aenter__(self):
            self.entered_sessions.append(self)
            return self

        async def __aexit__(self, exc_type, exc, tb):
            self.exited_sessions.append(self)
            return False

        def add(self, instance):
            self.added.append(instance)

        async def commit(self):
            self.commit_calls += 1

        async def refresh(self, instance):
            self.refresh_calls += 1
            self.refreshed.append(instance)

        async def rollback(self):
            self.rollback_calls += 1

    def create_session() -> RecordingAsyncSession:
        return RecordingAsyncSession()

    return create_session


@pytest.fixture
def override_current_user(test_app: FastAPI, fake_user_factory: Callable[..., SimpleNamespace]) -> Callable[..., SimpleNamespace]:
    """
    Fixture to override the current user dependency in the FastAPI test 
    application.
    """
    from app.core import dependencies

    def override(
        user=None,
        user_id: int = 1,
        username: str = "test-user",
        roles: str | list[str] | tuple[str, ...] = ("admin",),
    ) -> SimpleNamespace:
        current_user = user or fake_user_factory(
            user_id=user_id,
            username=username,
            roles=roles,
        )

        async def fake_get_current_user() -> Any | SimpleNamespace:
            return current_user

        test_app.dependency_overrides[dependencies.get_current_user] = fake_get_current_user
        return current_user

    return override


@pytest.fixture
def override_session(test_app: FastAPI) -> Callable[..., Any]:
    """
    Fixture to override the session dependency in the FastAPI test application.
    """
    from app.core import dependencies

    def override(session=None) -> Any:
        test_session = object() if session is None else session

        async def fake_get_session():
            yield test_session

        test_app.dependency_overrides[dependencies.get_session] = fake_get_session
        return test_session

    return override


@pytest.fixture
def allow_roles(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """
    Fixture to allow specific roles for the current user in the FastAPI 
    test application.
    """
    from app.core import dependencies

    def allow(*role_names: str):
        allowed_roles = set(role_names)

        async def fake_user_has_role(_user, role_name, _session) -> bool:
            return not allowed_roles or role_name in allowed_roles

        monkeypatch.setattr(dependencies, "user_has_role", fake_user_has_role)

    return allow


@pytest.fixture
def agent_parent_state_factory() -> Callable[..., dict[str, Any]]:
    """
    Fixture to create fresh parent negotiation states for agent unit tests.
    """
    def create_parent_state(**overrides: Any) -> dict[str, Any]:
        state = {
            "simulation_id": "10",
            "session_id": "10",
            "app_session_id": 44,
            "user_id": "7",
            "user_side": "side_b",
            "scenario_public_context": {"sentinel": "PUBLIC"},
            "side_a_private_context": {"sentinel": "SIDE_A_SECRET"},
            "side_b_private_context": {"sentinel": "SIDE_B_SECRET"},
            "counterpart_persona": {"sentinel": "PERSONA"},
            "side_a": {"sentinel": "RAW_SIDE_A"},
            "side_b": {"sentinel": "RAW_SIDE_B"},
            "messages": [{"role": "user", "content": "LATEST-STUDENT"}],
            "phase": "bargaining",
            "active_side": "side_b",
            "current_offer": {"terms": {"sentinel": "OFFER"}},
            "offer_history": [{"terms": {"sentinel": "HISTORY"}}],
            "coach_advice": {"sentinel": "COACH_SECRET"},
            "evaluation": {"sentinel": "EVALUATOR_SECRET"},
            "final_evaluation": {"sentinel": "FINAL_SECRET"},
            "retrieval_result": {"summary": "SHARED_RETRIEVAL"},
            "evidence_ledger": {
                "records": [
                    {"visibility_level": "learner", "summary": "LEARNER_VISIBLE"},
                    {"visibility_level": "teacher", "summary": "TEACHER_ONLY"},
                    {"visibility_level": "debug", "summary": "DEBUG_ONLY"},
                ],
            },
            "side_a_response": "COUNTERPART_RESPONSE",
            "turn_count": 2,
            "evaluation_mode": "rolling",
            "terminal_reason": None,
            "requested_action": None,
            "event_log": ["INTERNAL_EVENT"],
        }
        state.update(deepcopy(overrides))
        return state

    return create_parent_state


@pytest.fixture
def agent_parent_state(agent_parent_state_factory: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    """
    Fixture to provide a default fresh parent negotiation state.
    """
    return agent_parent_state_factory()


@pytest.fixture
def agent_evidence_ledger_factory() -> Callable[..., dict[str, Any]]:
    """
    Fixture to create fresh agent evidence ledger payloads.
    """
    def create_evidence_ledger(
        agent_name: str = "counterpart",
        steps: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            agent_name: {
                "pipeline": {
                    "steps": [] if steps is None else deepcopy(steps),
                },
            },
        }

    return create_evidence_ledger


@pytest.fixture
def agent_counterpart_payload() -> dict[str, Any]:
    """
    Fixture to provide a fresh structured counterpart response payload.
    """
    return {
        "side": "side_a",
        "message": "Counterpart reply",
        "action": "counter",
        "offer": {
            "side": "side_a",
            "price": None,
            "terms": {},
            "raw_text": "Counterpart reply",
        },
        "private_notes": {
            "strategy_used": "test",
            "reservation_value_check": "ok",
            "target_value_check": "ok",
            "risk": "low",
        },
    }


@pytest.fixture
def capturing_graph_factory() -> Callable[..., tuple[Any, dict[str, Any]]]:
    """
    Fixture to create graph fakes that capture invoked state.
    """
    def create_capturing_graph(result: Any) -> tuple[Any, dict[str, Any]]:
        captured: dict[str, Any] = {}

        class CapturingGraph:
            def __init__(self) -> None:
                self.payload = None

            def invoke(self, payload, config=None):
                self.payload = payload
                captured.update(payload)
                if callable(result):
                    return result(payload)
                return deepcopy(result)

        return CapturingGraph(), captured

    return create_capturing_graph
