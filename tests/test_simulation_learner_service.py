from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.schemas.simulation_learner_schemas import SimulationLearnerAskRequest
from app.services import simulation_learner_service


def _user(user_id=7):
    return SimpleNamespace(id=user_id, username=f"user-{user_id}", roles=[])


def _simulation(status="paused", phase="bargaining"):
    return SimpleNamespace(
        id=10,
        status=status,
        session_id=None,
        user_id_owner=7,
        user_id_participant=None,
        teacher_id=None,
        user_side="side_b",
        rag_profile_id=500,
        corpus_id=200,
        corpus_index_id=77,
        negotiation_state={
            "current_phase": phase,
            "user_side": "side_b",
            "data": {
                "simulation_id": "10",
                "session_id": "20",
                "app_session_id": 30,
                "user_id": "7",
                "user_side": "side_b",
                "phase": phase,
                "active_side": "side_b",
                "scenario_public_context": {"topic": "salary"},
                "side_a_private_context": {"secret": "COUNTERPART_SECRET"},
                "side_b_private_context": {"target": "STUDENT_TARGET"},
                "messages": [{"role": "user", "content": "Could you do 95?"}],
                "current_offer": {"price": 95},
                "offer_history": [{"price": 100}],
                "evaluation": {"secret": "EVALUATOR_ONLY"},
                "event_log": ["internal"],
            },
        },
        messages=[{"role": "user", "content": "Could you do 95?"}],
        last_updated=datetime.now(timezone.utc),
    )


class FakeLearnerAgent:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def invoke(self, payload, config=None):
        self.calls.append({"payload": payload, "config": config})
        return self.result


class FakeTavilySearch:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.mark.asyncio
async def test_ask_simulation_learner_returns_answer_and_safe_metadata(monkeypatch):
    captured = {}
    fake_agent = FakeLearnerAgent(
        {
            "messages": [
                {"role": "user", "content": "What should I do?"},
                {"role": "assistant", "content": "Anchor on objective criteria."},
            ]
        }
    )

    async def fake_get_retrieval_graph(simulation, session):
        return "crag", "retrieval-graph"

    def fake_build_llm(selection, run_name):
        captured["selection"] = selection
        captured["run_name"] = run_name
        return "learner-model"

    def fake_make_agent(**kwargs):
        captured["agent_kwargs"] = kwargs
        return fake_agent

    def fake_usage_context(**kwargs):
        captured["usage_context"] = kwargs
        return object(), object(), {"callbacks": ["usage"]}

    monkeypatch.setattr(
        simulation_learner_service,
        "_get_retrieval_graph_for_simulation",
        fake_get_retrieval_graph,
    )
    monkeypatch.setattr(simulation_learner_service, "_build_selected_llm", fake_build_llm)
    monkeypatch.setattr(simulation_learner_service, "make_learner_agent", fake_make_agent)
    monkeypatch.setattr(
        simulation_learner_service,
        "create_usage_tracking_context",
        fake_usage_context,
    )
    monkeypatch.setattr(
        simulation_learner_service,
        "summarize_usage_handler",
        lambda handler: {"totals": {"total_tokens": 12}, "models": {}},
    )
    monkeypatch.setattr(
        simulation_learner_service,
        "summarize_agent_token_usage_handler",
        lambda handler: {"simulation_learner": 12},
    )
    monkeypatch.setattr(simulation_learner_service.settings, "TAVILY_API_KEY", None)

    simulation = _simulation()
    original_state = repr(simulation.negotiation_state)
    original_messages = list(simulation.messages)

    result = await simulation_learner_service.ask_simulation_learner_srvc(
        simulation,
        SimulationLearnerAskRequest(
            query="What should I do?",
            learner_llm_provider="openai",
            learner_llm_model="gpt-4o-mini",
        ),
        object(),
        _user(),
    )

    assert result.simulation_id == 10
    assert result.status == "paused"
    assert result.answer == "Anchor on objective criteria."
    assert captured["selection"] == {"provider": "openai", "model": "gpt-4o-mini"}
    assert captured["run_name"] == "simulation.learner"
    assert captured["agent_kwargs"]["crag_graph"] == "retrieval-graph"
    assert captured["agent_kwargs"]["graph_rag_graph"] is None
    assert captured["agent_kwargs"]["messages"] == [{"role": "user", "content": "Could you do 95?"}]
    assert captured["agent_kwargs"]["user_side"] == "side_b"
    assert captured["agent_kwargs"]["student_private_context"]["target"] == "STUDENT_TARGET"
    assert "COUNTERPART_SECRET" not in repr(captured["agent_kwargs"])
    assert "EVALUATOR_ONLY" not in repr(captured["agent_kwargs"])
    assert fake_agent.calls[0]["payload"] == {
        "messages": [{"role": "user", "content": "What should I do?"}]
    }
    assert result.metadata["tools_available"] == [
        "crag_tool",
        "summarize_negotiation_history_tool",
    ]
    assert result.metadata["token_usage"] == {"simulation_learner": 12}
    assert repr(simulation.negotiation_state) == original_state
    assert simulation.messages == original_messages


@pytest.mark.asyncio
async def test_ask_simulation_learner_rejects_non_runnable_status():
    with pytest.raises(ValueError, match="Simulation must be active or paused"):
        await simulation_learner_service.ask_simulation_learner_srvc(
            _simulation(status="completed"),
            SimulationLearnerAskRequest(query="Can I ask?"),
            object(),
            _user(),
        )


@pytest.mark.asyncio
async def test_ask_simulation_learner_rejects_ended_phase():
    with pytest.raises(ValueError, match="Ended simulations cannot accept learner questions"):
        await simulation_learner_service.ask_simulation_learner_srvc(
            _simulation(phase="ended"),
            SimulationLearnerAskRequest(query="Can I ask?"),
            object(),
            _user(),
        )


@pytest.mark.asyncio
async def test_ask_simulation_learner_wires_graphrag_and_tavily(monkeypatch):
    captured = {}
    fake_agent = FakeLearnerAgent({"messages": [{"role": "assistant", "content": "Use web and graph context."}]})

    async def fake_get_retrieval_graph(simulation, session):
        return "graphrag", "graph-rag"

    def fake_make_agent(**kwargs):
        captured["agent_kwargs"] = kwargs
        return fake_agent

    def fake_tavily(**kwargs):
        captured["tavily_kwargs"] = kwargs
        return FakeTavilySearch(**kwargs)

    monkeypatch.setattr(
        simulation_learner_service,
        "_get_retrieval_graph_for_simulation",
        fake_get_retrieval_graph,
    )
    monkeypatch.setattr(
        simulation_learner_service,
        "_build_selected_llm",
        lambda selection, run_name: "learner-model",
    )
    monkeypatch.setattr(simulation_learner_service, "make_learner_agent", fake_make_agent)
    monkeypatch.setattr(simulation_learner_service, "TavilySearch", fake_tavily)
    monkeypatch.setattr(simulation_learner_service.settings, "TAVILY_API_KEY", "token")
    monkeypatch.setattr(
        simulation_learner_service,
        "create_usage_tracking_context",
        lambda **kwargs: (object(), object(), {}),
    )
    monkeypatch.setattr(
        simulation_learner_service,
        "summarize_usage_handler",
        lambda handler: {"totals": {"total_tokens": 0}, "models": {}},
    )
    monkeypatch.setattr(
        simulation_learner_service,
        "summarize_agent_token_usage_handler",
        lambda handler: {},
    )

    result = await simulation_learner_service.ask_simulation_learner_srvc(
        _simulation(),
        SimulationLearnerAskRequest(
            query="What changed this week?",
            max_results=3,
            include_images=True,
            include_answers=True,
        ),
        object(),
        _user(),
    )

    assert result.answer == "Use web and graph context."
    assert captured["agent_kwargs"]["crag_graph"] is None
    assert captured["agent_kwargs"]["graph_rag_graph"] == "graph-rag"
    assert captured["agent_kwargs"]["tavily_search"].kwargs["max_results"] == 3
    assert captured["agent_kwargs"]["tavily_search"].kwargs["include_images"] is True
    assert captured["agent_kwargs"]["tavily_search"].kwargs["include_answer"] is True
    assert captured["agent_kwargs"]["include_images"] is True
    assert captured["agent_kwargs"]["include_answers"] is True
    assert "tavily_search_tool" in result.metadata["tools_available"]
