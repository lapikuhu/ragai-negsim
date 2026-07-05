from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest

from app.schemas.simulation_learner_schemas import SimulationLearnerAskRequest
from app.services import simulation_learner_service, source_cards_service


def _user(user_id=7):
    return SimpleNamespace(id=user_id, username=f"user-{user_id}", roles=[])


def _learner_config(enabled=True):
    return {
        "enabled": enabled,
        "models": {
            "response": {"provider": "openai", "model": "gpt-4o-mini"},
            "negotiation_summary": {"provider": "openai", "model": "gpt-4.1-mini"},
            "tavily_summary": {"provider": "openai", "model": "gpt-4o-mini"},
        },
        "tavily": {
            "max_results": 5,
            "include_images": False,
            "include_answers": False,
        },
    }


def _simulation(status="paused", phase="bargaining", learner_config=None):
    if learner_config is None:
        learner_config = _learner_config()
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
                "learner_config": learner_config,
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


class FakeAIMessageWithToolCalls:
    type = "ai"

    def __init__(self, content, tool_calls):
        self.content = content
        self.tool_calls = tool_calls


class FakeToolMessage:
    type = "tool"

    def __init__(self, content, tool_call_id="tool-call-1", name="crag_tool"):
        self.content = content
        self.tool_call_id = tool_call_id
        self.name = name


def _patch_basic_learner_service(monkeypatch, agent_result, *, retrieval_strategy="crag", tavily_api_key=None):
    fake_agent = object()

    async def fake_get_retrieval_graph(simulation, session):
        return retrieval_strategy, "retrieval-graph"

    monkeypatch.setattr(
        simulation_learner_service,
        "_get_retrieval_graph_for_simulation",
        fake_get_retrieval_graph,
    )
    monkeypatch.setattr(
        simulation_learner_service,
        "_build_selected_llm",
        lambda selection, run_name: f"{run_name}:{selection['model']}",
    )
    monkeypatch.setattr(
        simulation_learner_service,
        "make_learner_agent",
        lambda **kwargs: fake_agent,
    )
    monkeypatch.setattr(
        simulation_learner_service,
        "invoke_simulation_learner_agent",
        lambda agent, question, config=None: agent_result,
    )
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
    monkeypatch.setattr(simulation_learner_service.settings, "TAVILY_API_KEY", tavily_api_key)


@pytest.mark.asyncio
async def test_ask_simulation_learner_returns_answer_and_safe_metadata(monkeypatch):
    captured = {"builds": []}
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
        captured["builds"].append((selection, run_name))
        return f"{run_name}:{selection['model']}"

    def fake_make_agent(**kwargs):
        captured["agent_kwargs"] = kwargs
        return fake_agent

    def fake_invoke_agent(agent, question, config=None):
        captured["invoke"] = {
            "agent": agent,
            "question": question,
            "config": config,
        }
        return fake_agent.result

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
        "invoke_simulation_learner_agent",
        fake_invoke_agent,
    )
    monkeypatch.setattr(
        simulation_learner_service,
        "create_usage_tracking_context",
        fake_usage_context,
    )
    monkeypatch.setattr(
        simulation_learner_service,
        "summarize_usage_handler",
        lambda handler: {"totals": {"total_tokens": 30}, "models": {}},
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
            chat_history=[
                {"role": "user", "content": "Earlier question?"},
                {"role": "assistant", "content": "Earlier answer."},
            ],
        ),
        object(),
        _user(),
    )

    assert result.simulation_id == 10
    assert result.status == "paused"
    assert result.answer == "Anchor on objective criteria."
    assert captured["builds"][:2] == [
        ({"provider": "openai", "model": "gpt-4o-mini"}, "simulation.learner"),
        ({"provider": "openai", "model": "gpt-4.1-mini"}, "simulation.learner.summary"),
    ]
    assert captured["agent_kwargs"]["crag_graph"] == "retrieval-graph"
    assert captured["agent_kwargs"]["graph_rag_graph"] is None
    assert captured["agent_kwargs"]["messages"] == [{"role": "user", "content": "Could you do 95?"}]
    assert captured["agent_kwargs"]["user_side"] == "side_b"
    assert captured["agent_kwargs"]["student_private_context"]["target"] == "STUDENT_TARGET"
    assert "COUNTERPART_SECRET" not in repr(captured["agent_kwargs"])
    assert "EVALUATOR_ONLY" not in repr(captured["agent_kwargs"])
    assert "Previous learner conversation" in captured["agent_kwargs"]["prompt_template"]
    assert "User: Earlier question?" in captured["agent_kwargs"]["prompt_template"]
    assert "Assistant: Earlier answer." in captured["agent_kwargs"]["prompt_template"]
    assert captured["invoke"]["agent"] is fake_agent
    assert captured["invoke"]["question"] == "What should I do?"
    assert captured["invoke"]["config"]["configurable"]["thread_id"] == "simulation-10-learner-user-7"
    assert result.metadata["tools_available"] == [
        "crag_tool",
        "summarize_negotiation_history_tool",
    ]
    assert result.metadata["token_usage"] == {"simulation_learner": 12}
    assert result.metadata["llm_usage"] == {"totals": {"total_tokens": 30}, "models": {}}
    assert result.metadata["answer_token_usage"] == {"total_tokens": 30}
    assert repr(simulation.negotiation_state) == original_state
    assert simulation.messages == original_messages


@pytest.mark.asyncio
async def test_ask_simulation_learner_includes_ordered_tool_call_names(monkeypatch):
    fake_agent = object()

    async def fake_get_retrieval_graph(simulation, session):
        return "crag", "retrieval-graph"

    def fake_invoke_agent(agent, question, config=None):
        return {
            "messages": [
                FakeAIMessageWithToolCalls(
                    "",
                    [
                        {"name": "crag_tool", "args": {"question": "ignored"}},
                        {"name": "tavily_search_tool", "args": {"query": "ignored"}},
                    ],
                ),
                FakeToolMessage("tool output must not be exposed"),
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"name": "crag_tool", "args": {"question": "ignored duplicate"}}
                    ],
                },
                {"role": "tool", "content": "dict tool output must not be exposed"},
                {"role": "assistant", "content": "Use objective criteria."},
            ]
        }

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
    monkeypatch.setattr(
        simulation_learner_service,
        "make_learner_agent",
        lambda **kwargs: fake_agent,
    )
    monkeypatch.setattr(
        simulation_learner_service,
        "invoke_simulation_learner_agent",
        fake_invoke_agent,
    )
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
    monkeypatch.setattr(simulation_learner_service.settings, "TAVILY_API_KEY", None)

    result = await simulation_learner_service.ask_simulation_learner_srvc(
        _simulation(),
        SimulationLearnerAskRequest(query="What tools did you use?"),
        object(),
        _user(),
    )

    assert result.answer == "Use objective criteria."
    assert result.metadata["tool_calls"] == [
        "crag_tool",
        "tavily_search_tool",
        "crag_tool",
    ]
    assert "tool output must not be exposed" not in repr(result.metadata["tool_calls"])
    assert result.metadata["tools_available"] == [
        "crag_tool",
        "summarize_negotiation_history_tool",
    ]


@pytest.mark.asyncio
async def test_ask_simulation_learner_uses_structured_response_metadata(monkeypatch):
    _patch_basic_learner_service(
        monkeypatch,
        {
            "structured_response": {
                "answer": "Use objective criteria from the role facts.",
                "tool_decision_summary": "Used CRAG because the user requested retrieval.",
                "evidence_used": ["student_private_context", "crag_tool"],
                "confidence": "high",
            },
            "messages": [
                {"role": "assistant", "content": "Raw structured content should not win."}
            ],
        },
    )

    result = await simulation_learner_service.ask_simulation_learner_srvc(
        _simulation(),
        SimulationLearnerAskRequest(query="Use CRAG to define BATNA."),
        object(),
        _user(),
    )

    assert result.answer == "Use objective criteria from the role facts."
    assert result.metadata["learner_structured_output"] == {
        "answer": "Use objective criteria from the role facts.",
        "tool_decision_summary": "Used CRAG because the user requested retrieval.",
        "evidence_used": ["student_private_context", "crag_tool"],
        "confidence": "high",
    }


@pytest.mark.asyncio
async def test_ask_simulation_learner_parses_structured_json_final_content(monkeypatch):
    structured_json = {
        "answer": "BATNA is your best available fallback if no deal is reached.",
        "tool_decision_summary": "Answered from local knowledge because no tool was requested.",
        "evidence_used": ["standard_negotiation_knowledge"],
        "confidence": "medium",
    }
    _patch_basic_learner_service(
        monkeypatch,
        {
            "messages": [
                {"role": "assistant", "content": json.dumps(structured_json)}
            ],
        },
    )

    result = await simulation_learner_service.ask_simulation_learner_srvc(
        _simulation(),
        SimulationLearnerAskRequest(query="Define BATNA."),
        object(),
        _user(),
    )

    assert result.answer == "BATNA is your best available fallback if no deal is reached."
    assert result.metadata["learner_structured_output"] == structured_json


@pytest.mark.asyncio
async def test_ask_simulation_learner_defaults_structured_output_for_plain_text(monkeypatch):
    _patch_basic_learner_service(
        monkeypatch,
        {"messages": [{"role": "assistant", "content": "Plain answer."}]},
    )

    result = await simulation_learner_service.ask_simulation_learner_srvc(
        _simulation(),
        SimulationLearnerAskRequest(query="What should I do?"),
        object(),
        _user(),
    )

    assert result.answer == "Plain answer."
    assert result.metadata["learner_structured_output"] == {
        "answer": "Plain answer.",
        "tool_decision_summary": "Structured learner output was not returned.",
        "evidence_used": [],
        "confidence": "medium",
    }


@pytest.mark.asyncio
async def test_ask_simulation_learner_debug_trace_includes_tool_calls_results_and_request(monkeypatch):
    _patch_basic_learner_service(
        monkeypatch,
        {
            "messages": [
                FakeAIMessageWithToolCalls(
                    "",
                    [
                        {
                            "id": "call-1",
                            "name": "tavily_search_tool",
                            "args": {"query": "BATNA definition negotiation", "max_results": 5},
                        }
                    ],
                ),
                FakeToolMessage(
                    "full tavily output",
                    tool_call_id="call-1",
                    name="tavily_search_tool",
                ),
                {"role": "assistant", "content": "Use your BATNA as leverage."},
            ],
        },
        tavily_api_key="token",
    )

    result = await simulation_learner_service.ask_simulation_learner_srvc(
        _simulation(),
        SimulationLearnerAskRequest(query="Please use Tavily to define BATNA."),
        object(),
        _user(),
    )

    debug_trace = result.metadata["learner_debug_trace"]
    assert debug_trace["explicit_tool_request"] == {
        "requested": True,
        "tool_names": ["tavily_search_tool"],
        "unavailable_tool_names": [],
    }
    assert debug_trace["events"] == [
        {
            "type": "tool_call",
            "tool_name": "tavily_search_tool",
            "tool_call_id": "call-1",
            "args": {"query": "BATNA definition negotiation", "max_results": 5},
        },
        {
            "type": "tool_result",
            "tool_name": "tavily_search_tool",
            "tool_call_id": "call-1",
            "status": "success",
            "content": "full tavily output",
            "content_length": 18,
        },
    ]


@pytest.mark.asyncio
async def test_ask_simulation_learner_returns_enriched_crag_sources(monkeypatch):
    source_payload = {
        "status": "success",
        "answer": "Use objective criteria.",
        "sources": [
            {
                "rank": 1,
                "raw_document_id": 3,
                "document_chunk_id": 7,
                "chunk_index": 2,
                "source": "C:/docs/negotiation-guide.pdf",
                "rerank_score": 0.91,
                "excerpt": "Objective criteria can anchor negotiation choices.",
            }
        ],
    }
    _patch_basic_learner_service(
        monkeypatch,
        {
            "messages": [
                FakeAIMessageWithToolCalls(
                    "",
                    [{"id": "call-1", "name": "crag_tool", "args": {"question": "BATNA"}}],
                ),
                FakeToolMessage(
                    json.dumps(source_payload),
                    tool_call_id="call-1",
                    name="crag_tool",
                ),
                {"role": "assistant", "content": "Use objective criteria."},
            ],
        },
    )

    async def fake_get_raw_document_by_id(raw_document_id, session):
        assert raw_document_id == 3
        return SimpleNamespace(
            id=3,
            name="Negotiation Guide",
            document_title="Getting to Yes",
            document_author="Roger Fisher and William Ury",
            document_year=1981,
        )

    monkeypatch.setattr(
        source_cards_service,
        "raw_documents_repo",
        SimpleNamespace(get_raw_document_by_id=fake_get_raw_document_by_id),
        raising=False,
    )

    result = await simulation_learner_service.ask_simulation_learner_srvc(
        _simulation(),
        SimulationLearnerAskRequest(query="Use CRAG for BATNA."),
        object(),
        _user(),
    )

    assert result.sources == [
        {
            "rank": 1,
            "raw_document_id": 3,
            "raw_document_name": "Negotiation Guide",
            "document_title": "Getting to Yes",
            "document_author": "Roger Fisher and William Ury",
            "document_year": 1981,
            "document_chunk_id": 7,
            "chunk_index": 2,
            "source": "C:/docs/negotiation-guide.pdf",
            "rerank_score": 0.91,
            "excerpt": "Objective criteria can anchor negotiation choices.",
        }
    ]


@pytest.mark.asyncio
async def test_ask_simulation_learner_returns_enriched_graphrag_sources(monkeypatch):
    source_payload = {
        "status": "success",
        "answer": "Graph evidence supports anchoring on objective criteria.",
        "sources": [
            {
                "rank": 1,
                "raw_document_id": 4,
                "document_chunk_id": 8,
                "chunk_index": 3,
                "source": "C:/docs/graph-guide.pdf",
                "score": 0.88,
                "retrieval_strategy": "graphrag",
                "retrieval_mode": "semantic",
                "graph_id": 12,
                "graph_generation": "gen-1",
                "evidence_path": "semantic",
                "excerpt": "Graph evidence supports objective criteria.",
            }
        ],
    }
    _patch_basic_learner_service(
        monkeypatch,
        {
            "messages": [
                FakeAIMessageWithToolCalls(
                    "",
                    [{"id": "call-1", "name": "graph_rag_tool", "args": {"question": "BATNA"}}],
                ),
                FakeToolMessage(
                    json.dumps(source_payload),
                    tool_call_id="call-1",
                    name="graph_rag_tool",
                ),
                {"role": "assistant", "content": "Use objective criteria."},
            ],
        },
        retrieval_strategy="graphrag",
    )

    async def fake_get_raw_document_by_id(raw_document_id, session):
        assert raw_document_id == 4
        return SimpleNamespace(
            id=4,
            name="Graph Guide",
            document_title="Graph Grounding",
            document_author="Ada Lovelace",
            document_year=2026,
        )

    monkeypatch.setattr(
        source_cards_service,
        "raw_documents_repo",
        SimpleNamespace(get_raw_document_by_id=fake_get_raw_document_by_id),
        raising=False,
    )

    result = await simulation_learner_service.ask_simulation_learner_srvc(
        _simulation(),
        SimulationLearnerAskRequest(query="Use GraphRAG for BATNA."),
        object(),
        _user(),
    )

    assert result.sources == [
        {
            "rank": 1,
            "raw_document_id": 4,
            "raw_document_name": "Graph Guide",
            "document_title": "Graph Grounding",
            "document_author": "Ada Lovelace",
            "document_year": 2026,
            "document_chunk_id": 8,
            "chunk_index": 3,
            "source": "C:/docs/graph-guide.pdf",
            "score": 0.88,
            "retrieval_strategy": "graphrag",
            "retrieval_mode": "semantic",
            "graph_id": 12,
            "graph_generation": "gen-1",
            "evidence_path": "semantic",
            "excerpt": "Graph evidence supports objective criteria.",
        }
    ]


@pytest.mark.asyncio
async def test_ask_simulation_learner_records_unavailable_requested_tool(monkeypatch):
    _patch_basic_learner_service(
        monkeypatch,
        {"messages": [{"role": "assistant", "content": "GraphRAG is unavailable here."}]},
    )

    result = await simulation_learner_service.ask_simulation_learner_srvc(
        _simulation(),
        SimulationLearnerAskRequest(query="Use GraphRAG to define BATNA."),
        object(),
        _user(),
    )

    assert result.metadata["learner_debug_trace"]["explicit_tool_request"] == {
        "requested": True,
        "tool_names": [],
        "unavailable_tool_names": ["graph_rag_tool"],
    }


@pytest.mark.asyncio
async def test_ask_simulation_learner_rejects_disabled_learner_config():
    with pytest.raises(ValueError, match="Learning agent is not enabled"):
        await simulation_learner_service.ask_simulation_learner_srvc(
            _simulation(learner_config=_learner_config(enabled=False)),
            SimulationLearnerAskRequest(query="Can I ask?"),
            object(),
            _user(),
        )


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
    assert captured["agent_kwargs"]["tavily_search"].kwargs["tavily_api_key"] == "token"
    assert captured["agent_kwargs"]["include_images"] is True
    assert captured["agent_kwargs"]["include_answers"] is True
    assert "tavily_search_tool" in result.metadata["tools_available"]


@pytest.mark.asyncio
async def test_ask_simulation_learner_uses_stored_models_and_tavily_defaults(monkeypatch):
    captured = {"builds": []}
    fake_agent = FakeLearnerAgent({"messages": [{"role": "assistant", "content": "Stored config answer."}]})

    async def fake_get_retrieval_graph(simulation, session):
        return "crag", "retrieval"

    def fake_build_llm(selection, run_name):
        captured["builds"].append((selection, run_name))
        return f"{run_name}:{selection['model']}"

    def fake_make_agent(**kwargs):
        captured["agent_kwargs"] = kwargs
        return fake_agent

    def fake_tavily(**kwargs):
        captured["tavily_kwargs"] = kwargs
        return FakeTavilySearch(**kwargs)

    learner_config = _learner_config()
    learner_config["tavily"] = {
        "max_results": 2,
        "include_images": True,
        "include_answers": True,
    }
    monkeypatch.setattr(
        simulation_learner_service,
        "_get_retrieval_graph_for_simulation",
        fake_get_retrieval_graph,
    )
    monkeypatch.setattr(simulation_learner_service, "_build_selected_llm", fake_build_llm)
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
        _simulation(learner_config=learner_config),
        SimulationLearnerAskRequest(query="Use stored config"),
        object(),
        _user(),
    )

    assert result.answer == "Stored config answer."
    assert captured["builds"] == [
        ({"provider": "openai", "model": "gpt-4o-mini"}, "simulation.learner"),
        ({"provider": "openai", "model": "gpt-4.1-mini"}, "simulation.learner.summary"),
        ({"provider": "openai", "model": "gpt-4o-mini"}, "simulation.learner.tavily_summary"),
    ]
    assert captured["agent_kwargs"]["model"] == "simulation.learner:gpt-4o-mini"
    assert captured["agent_kwargs"]["summarize_model"] == "simulation.learner.summary:gpt-4.1-mini"
    assert captured["agent_kwargs"]["tavily_summarizer_model"] == "simulation.learner.tavily_summary:gpt-4o-mini"
    assert captured["tavily_kwargs"] == {
        "max_results": 2,
        "include_images": True,
        "include_answer": True,
        "tavily_api_key": "token",
    }
