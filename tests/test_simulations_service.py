from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.schemas.simulations_schemas import (
    SimulationCreate,
    SimulationCreateRequest,
    SimulationProxyDisableResponse,
    SimulationProxyTurnRequest,
    SimulationProxyTurnResponse,
    SimulationReadWithState,
    SimulationStartRequest,
    SimulationTeacherReviewRequest,
    SimulationTurnRequest,
    SimulationTurnResponse,
    SimulationUpdateRequest,
)
from app.services import simulations_service


def _user(user_id=1):
    return SimpleNamespace(id=user_id, username=f"user-{user_id}", roles=[])


def _admin(user_id=1):
    return SimpleNamespace(
        id=user_id,
        username=f"user-{user_id}",
        roles=[SimpleNamespace(name="admin")],
    )


def _internal_state_with_secrets():
    return {
        "simulation_id": "10",
        "user_side": "side_b",
        "phase": "bargaining",
        "scenario_public_context": {"sentinel": "PUBLIC"},
        "side_a_private_context": {"sentinel": "SIDE_A_SECRET"},
        "side_b_private_context": {"sentinel": "SIDE_B_SECRET"},
        "side_a": {"sentinel": "RAW_SIDE_A"},
        "side_b": {"sentinel": "RAW_SIDE_B"},
        "counterpart_persona": {"sentinel": "PERSONA_SECRET"},
        "messages": [{"role": "user", "content": "Offer"}],
        "current_offer": {"terms": {"time": "14:00"}},
        "offer_history": [],
        "coach_advice": {"summary": "Coach safely"},
        "evaluation": {"sentinel": "ROLLING_EVALUATION_SECRET"},
        "retrieval_result": {"sentinel": "RETRIEVAL_SECRET"},
        "event_log": ["INTERNAL_EVENT"],
        "evaluator_validation_error": "INTERNAL_ERROR",
        "turn_count": 2,
        "should_pause": True,
        "pause_reason": "counterpart_response_ready",
        "final_evaluation": {},
    }


def _simulation(
    simulation_id=10,
    status="created",
    session_id=None,
    user_id_owner=1,
    user_id_participant=None,
    scenario_id=100,
    corpus_id=200,
    corpus_index_id=77,
    coach_prompt_id=None,
    counterpart_prompt_id=None,
    evaluator_prompt_id=None,
    rag_profile_id=500,
    counter_part_side_persona_id=300,
    user_side="side_a",
    negotiation_state=None,
    messages=None,
):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=simulation_id,
        name=f"simulation-{simulation_id}",
        description="A negotiation simulation",
        status=status,
        session_id=session_id,
        user_id_owner=user_id_owner,
        user_id_participant=user_id_participant,
        scenario_id=scenario_id,
        corpus_id=corpus_id,
        corpus_index_id=corpus_index_id,
        coach_prompt_id=coach_prompt_id,
        counterpart_prompt_id=counterpart_prompt_id,
        evaluator_prompt_id=evaluator_prompt_id,
        rag_profile_id=rag_profile_id,
        counter_part_side_persona_id=counter_part_side_persona_id,
        user_side=user_side,
        teacher_reviewed=False,
        teacher_id=None,
        teacher_feedback=None,
        reviewed_at=None,
        created_at=now,
        last_updated=now,
        negotiation_state=negotiation_state or {},
        messages=messages or [],
        model_dump=lambda: {
            "id": simulation_id,
            "name": f"simulation-{simulation_id}",
            "description": "A negotiation simulation",
            "status": status,
            "session_id": session_id,
            "user_id_owner": user_id_owner,
            "user_id_participant": user_id_participant,
            "scenario_id": scenario_id,
            "corpus_id": corpus_id,
            "corpus_index_id": corpus_index_id,
            "coach_prompt_id": coach_prompt_id,
            "counterpart_prompt_id": counterpart_prompt_id,
            "evaluator_prompt_id": evaluator_prompt_id,
            "rag_profile_id": rag_profile_id,
            "counter_part_side_persona_id": counter_part_side_persona_id,
            "user_side": user_side,
            "teacher_reviewed": False,
            "teacher_id": None,
            "teacher_feedback": None,
            "reviewed_at": None,
            "created_at": now,
            "last_updated": now,
            "negotiation_state": negotiation_state or {},
            "messages": messages or [],
        },
    )


def _review_row(
    simulation_id=10,
    *,
    teacher_id=1,
    teacher_feedback="Strong reflection",
    reviewed_at=None,
    user_id_owner=1,
    user_id_participant=None,
    scenario_id=100,
    name=None,
    last_updated=None,
):
    now = reviewed_at or datetime.now(timezone.utc)
    simulation = _simulation(
        simulation_id=simulation_id,
        status="completed",
        user_id_owner=user_id_owner,
        user_id_participant=user_id_participant,
        scenario_id=scenario_id,
    )
    simulation.name = name or f"simulation-{simulation_id}"
    simulation.teacher_id = teacher_id
    simulation.teacher_feedback = teacher_feedback
    simulation.teacher_reviewed = True
    simulation.reviewed_at = now
    simulation.last_updated = last_updated or now
    return simulation


def test_turn_request_accepts_structured_action():
    request = SimulationTurnRequest(message="Please finish.", action="end")
    assert request.action == "end"


def test_proxy_turn_request_accepts_duration_and_nullable_persona():
    request = SimulationProxyTurnRequest(persona_id=None, duration="this_turn")
    assert request.persona_id is None
    assert request.duration == "this_turn"


def test_public_graph_state_is_positive_allow_list():
    public = simulations_service._public_graph_state(_internal_state_with_secrets())
    serialized = repr(public)

    assert "PUBLIC" in serialized
    assert "Coach safely" in serialized
    assert "SIDE_A_SECRET" not in serialized
    assert "SIDE_B_SECRET" not in serialized
    assert "ROLLING_EVALUATION_SECRET" not in serialized
    assert "INTERNAL_EVENT" not in serialized
    assert "INTERNAL_ERROR" not in serialized


def test_public_graph_state_includes_final_evaluation_only_after_end():
    internal = _internal_state_with_secrets()
    internal["final_evaluation"] = {"reasoning": "FINAL DEBRIEF"}

    active = simulations_service._public_graph_state(internal)
    internal["phase"] = "ended"
    ended = simulations_service._public_graph_state(internal)

    assert "final_evaluation" not in active
    assert ended["final_evaluation"]["reasoning"] == "FINAL DEBRIEF"


def test_public_graph_state_includes_intent_classification_when_present():
    internal = _internal_state_with_secrets()
    internal["intent_classification"] = {
        "intent": "continue",
        "confidence": "high",
        "reasoning": "Agreement language is not a stop request.",
    }

    public = simulations_service._public_graph_state(internal)

    assert public["intent_classification"]["intent"] == "continue"
    assert "event_log" not in public


def test_public_graph_state_exposes_safe_proxy_status_only():
    internal = _internal_state_with_secrets()
    internal["auto_user_proxy_enabled"] = True
    internal["user_proxy_persona"] = {
        "id": 300,
        "name": "Firm seller",
        "description": "Persona context",
    }
    internal["user_proxy_persona_id"] = 300

    public = simulations_service._public_graph_state(internal)

    assert public["auto_user_proxy_enabled"] is True
    assert public["user_proxy_persona"]["name"] == "Firm seller"
    assert public["user_proxy_persona_id"] == 300
    assert "description" not in public["user_proxy_persona"]


def _patch_runtime_context_repositories(
    monkeypatch,
    *,
    corpus=None,
    corpus_index=None,
    prompts=None,
    scenario=None,
    persona=None,
    app_session=None,
):
    if corpus is None:
        corpus = SimpleNamespace(id=200, name="Negotiation corpus", description="Corpus context")
    if scenario is None:
        scenario = SimpleNamespace(
            id=100,
            name="Salary scenario",
            description="AUTHORING-ONLY-DESCRIPTION",
            public_context={"topic": "salary negotiation"},
            side_a_private_context={"reservation": "SIDE-A-SECRET"},
            side_b_private_context={"reservation": "SIDE-B-SECRET"},
        )
    if corpus_index is None:
        corpus_index = SimpleNamespace(
            id=77,
            name="Negotiation index",
            description="Index context",
            corpus_id=200,
            vector_store_id=12,
            status="built",
            embedding_model="mini-l6-v2",
            embedding_dimensions=384,
            vector_namespace="corpus-index-77",
        )
    if persona is None:
        persona = SimpleNamespace(id=300, name="Firm seller", description="Persona context")
    if prompts is None:
        prompts = {}

    async def fake_get_corpus_by_id(corpus_id, session):
        return corpus

    async def fake_get_scenario_by_id(scenario_id, session):
        return scenario

    async def fake_get_corpus_index_by_id(corpus_index_id, session):
        return corpus_index

    async def fake_get_counterpart_persona_by_id(persona_id, session):
        return persona

    async def fake_get_session_by_id(session_id, session):
        return app_session

    async def fake_get_prompt_by_id(prompt_id, session):
        return prompts.get(prompt_id)

    monkeypatch.setattr(simulations_service.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)
    monkeypatch.setattr(
        simulations_service.corpus_indices_repo,
        "get_corpus_index_by_id",
        fake_get_corpus_index_by_id,
    )
    monkeypatch.setattr(simulations_service.scenarios_repo, "get_scenario_by_id", fake_get_scenario_by_id)
    monkeypatch.setattr(
        simulations_service.counterpart_personas_repo,
        "get_counterpart_persona_by_id",
        fake_get_counterpart_persona_by_id,
    )
    monkeypatch.setattr(simulations_service.sessions_repo, "get_session_by_id", fake_get_session_by_id)
    monkeypatch.setattr(simulations_service.prompts_repo, "get_prompt_by_id", fake_get_prompt_by_id)


@pytest.mark.asyncio
async def test_create_simulation_stamps_current_user(monkeypatch):
    captured = []
    created = _simulation(
        user_id_owner=7,
        coach_prompt_id=11,
        counterpart_prompt_id=12,
        evaluator_prompt_id=13,
    )

    async def fake_get_corpus_index_by_id(corpus_index_id, session):
        return SimpleNamespace(id=corpus_index_id, corpus_id=200, status="built")

    async def fake_get_prompt_by_id(prompt_id, session):
        prompts = {
            11: SimpleNamespace(id=11, messages={"template": "Coach {phase}"}),
            12: SimpleNamespace(id=12, messages={"template": "Counterpart {phase}"}),
            13: SimpleNamespace(id=13, messages={"template": "Evaluator {phase}"}),
        }
        return prompts.get(prompt_id)

    async def fake_get_rag_profile_by_id(profile_id, session):
        return SimpleNamespace(
            id=profile_id,
            strategy="crag",
            config={
                "top_k": 4,
                "reranker": "cross_encoder",
                "top_n": 3,
                "max_rewrite_attempts": 2,
            },
        )

    async def fake_create_simulation(simulation_in, session):
        captured.append(simulation_in)
        return created

    monkeypatch.setattr(
        simulations_service.corpus_indices_repo,
        "get_corpus_index_by_id",
        fake_get_corpus_index_by_id,
    )
    monkeypatch.setattr(
        simulations_service.prompts_repo,
        "get_prompt_by_id",
        fake_get_prompt_by_id,
    )
    monkeypatch.setattr(
        simulations_service.rag_profiles_repo,
        "get_rag_profile_by_id",
        fake_get_rag_profile_by_id,
    )
    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "create_simulation",
        fake_create_simulation,
    )

    result = await simulations_service.create_simulation_srvc(
        SimulationCreateRequest(
            name="Salary negotiation",
            description="Practice pay discussions",
            corpus_id=200,
            corpus_index_id=77,
            rag_profile_id=500,
            coach_prompt_id=11,
            counterpart_prompt_id=12,
            evaluator_prompt_id=13,
            scenario_id=100,
            counter_part_side_persona_id=300,
            user_side="side_a",
        ),
        object(),
        _user(7),
    )

    assert result.user_id_owner == 7
    assert result.corpus_index_id == 77
    assert result.coach_prompt_id == 11
    assert captured == [
        SimulationCreate(
            name="Salary negotiation",
            description="Practice pay discussions",
            user_id_owner=7,
            corpus_id=200,
            corpus_index_id=77,
            rag_profile_id=500,
            coach_prompt_id=11,
            counterpart_prompt_id=12,
            evaluator_prompt_id=13,
            session_id=None,
            user_id_participant=None,
            scenario_id=100,
            counter_part_side_persona_id=300,
            user_side="side_a",
        )
    ]


@pytest.mark.asyncio
async def test_create_simulation_requires_matching_built_corpus_index(monkeypatch):
    async def fake_get_corpus_index_by_id(corpus_index_id, session):
        return SimpleNamespace(id=corpus_index_id, corpus_id=999, status="built")

    monkeypatch.setattr(
        simulations_service.corpus_indices_repo,
        "get_corpus_index_by_id",
        fake_get_corpus_index_by_id,
    )

    with pytest.raises(ValueError, match="Corpus index does not belong"):
        await simulations_service.create_simulation_srvc(
            SimulationCreateRequest(
                name="Salary negotiation",
                corpus_id=200,
                corpus_index_id=77,
                rag_profile_id=500,
            ),
            object(),
            _user(7),
        )


@pytest.mark.asyncio
async def test_create_simulation_requires_existing_prompt(monkeypatch):
    async def fake_get_corpus_index_by_id(corpus_index_id, session):
        return SimpleNamespace(id=corpus_index_id, corpus_id=200, status="built")

    async def fake_get_prompt_by_id(prompt_id, session):
        return None

    async def fake_get_rag_profile_by_id(profile_id, session):
        return SimpleNamespace(
            id=profile_id,
            strategy="crag",
            config={
                "top_k": 4,
                "reranker": "cross_encoder",
                "top_n": 3,
                "max_rewrite_attempts": 2,
            },
        )

    monkeypatch.setattr(
        simulations_service.corpus_indices_repo,
        "get_corpus_index_by_id",
        fake_get_corpus_index_by_id,
    )
    monkeypatch.setattr(
        simulations_service.prompts_repo,
        "get_prompt_by_id",
        fake_get_prompt_by_id,
    )
    monkeypatch.setattr(
        simulations_service.rag_profiles_repo,
        "get_rag_profile_by_id",
        fake_get_rag_profile_by_id,
    )

    with pytest.raises(ValueError, match="Coach prompt not found"):
        await simulations_service.create_simulation_srvc(
            SimulationCreateRequest(
                name="Salary negotiation",
                corpus_id=200,
                corpus_index_id=77,
                rag_profile_id=500,
                coach_prompt_id=11,
            ),
            object(),
            _user(7),
        )


@pytest.mark.asyncio
async def test_create_simulation_requires_existing_rag_profile(monkeypatch):
    async def fake_get_corpus_index_by_id(corpus_index_id, session):
        return SimpleNamespace(id=corpus_index_id, corpus_id=200, status="built")

    async def fake_get_rag_profile_by_id(profile_id, session):
        return None

    monkeypatch.setattr(
        simulations_service.corpus_indices_repo,
        "get_corpus_index_by_id",
        fake_get_corpus_index_by_id,
    )
    monkeypatch.setattr(
        simulations_service.rag_profiles_repo,
        "get_rag_profile_by_id",
        fake_get_rag_profile_by_id,
    )

    with pytest.raises(ValueError, match="RAG profile not found"):
        await simulations_service.create_simulation_srvc(
            SimulationCreateRequest(
                name="Salary negotiation",
                corpus_id=200,
                corpus_index_id=77,
                rag_profile_id=500,
            ),
            object(),
            _user(7),
        )


@pytest.mark.asyncio
async def test_list_simulations_passes_filters_and_converts(monkeypatch):
    captured = []
    simulations = [_simulation(1), _simulation(2)]

    async def fake_list_simulations(
        session,
        skip=0,
        limit=20,
        status=None,
        owner_id=None,
        participant_id=None,
        teacher_id=None,
        corpus_id=None,
        corpus_index_id=None,
        rag_profile_id=None,
        coach_prompt_id=None,
        counterpart_prompt_id=None,
        evaluator_prompt_id=None,
        session_id=None,
        scenario_id=None,
    ):
        captured.append(
            (
                skip,
                limit,
                status,
                owner_id,
                participant_id,
                teacher_id,
                corpus_id,
                corpus_index_id,
                rag_profile_id,
                coach_prompt_id,
                counterpart_prompt_id,
                evaluator_prompt_id,
                session_id,
                scenario_id,
            )
        )
        return simulations

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "list_simulations",
        fake_list_simulations,
    )

    result = await simulations_service.list_simulations_srvc(
        object(),
        skip=5,
        limit=10,
        status="active",
        owner_id=3,
        participant_id=4,
        corpus_id=200,
        corpus_index_id=77,
        coach_prompt_id=11,
        counterpart_prompt_id=12,
        evaluator_prompt_id=13,
        session_id=8,
        scenario_id=100,
    )

    assert captured == [(5, 10, "active", 3, 4, None, 200, 77, None, 11, 12, 13, 8, 100)]
    assert [simulation.id for simulation in result] == [1, 2]


@pytest.mark.asyncio
async def test_list_simulations_filters_inaccessible_records_for_non_admin(monkeypatch):
    simulations = [
        _simulation(1, user_id_owner=7),
        _simulation(2, user_id_participant=7),
        _simulation(3, user_id_owner=99, user_id_participant=100),
    ]

    async def fake_list_simulations(**kwargs):
        return simulations

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "list_simulations",
        fake_list_simulations,
    )

    student_result = await simulations_service.list_simulations_srvc(
        object(),
        current_user=_user(7),
    )
    admin_result = await simulations_service.list_simulations_srvc(
        object(),
        current_user=_admin(9),
    )

    assert [simulation.id for simulation in student_result] == [1, 2]
    assert [simulation.id for simulation in admin_result] == [1, 2, 3]


@pytest.mark.asyncio
async def test_update_simulation_does_not_patch_graph_state(monkeypatch):
    captured = []
    updated = _simulation(status="paused")

    async def fake_update_simulation(simulation, simulation_in, session):
        captured.append(simulation_in)
        return updated

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )

    result = await simulations_service.update_simulation_srvc(
        _simulation(status="active"),
        SimulationUpdateRequest(name="Updated simulation", status="paused"),
        object(),
    )

    assert result.status == "paused"
    assert captured[0].model_dump(exclude_unset=True) == {
        "name": "Updated simulation",
        "status": "paused",
    }


@pytest.mark.asyncio
async def test_start_simulation_initializes_graph_state_and_activates(monkeypatch):
    captured_status = []
    simulation = _simulation(
        status="created",
        user_id_owner=7,
        coach_prompt_id=11,
        counterpart_prompt_id=12,
        evaluator_prompt_id=13,
    )
    _patch_runtime_context_repositories(
        monkeypatch,
        prompts={
            11: SimpleNamespace(id=11, name="Coach prompt", description="Coach", messages={"template": "Coach"}),
            12: SimpleNamespace(id=12, name="Counterpart prompt", description="Counterpart", messages={"template": "Counterpart"}),
            13: SimpleNamespace(id=13, name="Evaluator prompt", description="Evaluator", messages={"template": "Evaluator"}),
        },
    )

    async def fake_update_simulation(simulation_obj, simulation_in, session):
        simulation_obj.negotiation_state = simulation_in.negotiation_state.model_dump()
        simulation_obj.messages = [message.model_dump() for message in simulation_in.messages]
        simulation_obj.status = simulation_in.status
        return simulation_obj

    async def fake_update_status(simulation_obj, status_in, session):
        captured_status.append(status_in.status)
        simulation_obj.status = status_in.status
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )
    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation_status",
        fake_update_status,
    )

    result = await simulations_service.start_simulation_srvc(
        simulation,
        SimulationStartRequest(
            side_a={"name": "Buyer", "role": "buyer"},
            side_b={"name": "Seller", "role": "seller"},
        ),
        object(),
        _user(7),
    )

    assert isinstance(result, SimulationReadWithState)
    assert result.status == "active"
    assert result.negotiation_state.user_side == "side_a"
    assert result.negotiation_state.current_phase == "opening"
    assert result.negotiation_state.data["scenario_public_context"] == {
        "id": 100,
        "name": "Salary scenario",
        "topic": "salary negotiation",
    }
    assert "side_a" not in result.negotiation_state.data
    assert "side_b" not in result.negotiation_state.data
    assert "corpus_context" not in result.negotiation_state.data
    assert "counterpart_persona_context" not in result.negotiation_state.data
    assert "side_a_private_context" not in result.negotiation_state.data
    assert "side_b_private_context" not in result.negotiation_state.data
    internal = simulation.negotiation_state["data"]
    assert internal["side_a"]["name"] == "Buyer"
    assert internal["side_b"]["name"] == "Seller"
    assert internal["corpus_context"] == {
        "id": 200,
        "name": "Negotiation corpus",
        "description": "Corpus context",
    }
    assert internal["corpus_index_context"]["id"] == 77
    assert internal["corpus_index_context"]["name"] == "Negotiation index"
    assert internal["coach_prompt_context"]["name"] == "Coach prompt"
    assert internal["counterpart_prompt_context"]["name"] == "Counterpart prompt"
    assert internal["evaluator_prompt_context"]["name"] == "Evaluator prompt"
    assert internal["counterpart_persona_context"]["name"] == "Firm seller"
    assert internal["scenario_public_context"] == {
        "id": 100,
        "name": "Salary scenario",
        "topic": "salary negotiation",
    }
    assert internal["side_a_private_context"]["reservation"] == "SIDE-A-SECRET"
    assert internal["side_b_private_context"]["reservation"] == "SIDE-B-SECRET"
    assert "scenario_context" not in internal
    assert "AUTHORING-ONLY-DESCRIPTION" not in str(internal)
    assert internal["messages"] == []
    assert result.messages == []
    assert captured_status == []


@pytest.mark.asyncio
async def test_start_simulation_uses_persona_as_counterpart_default(monkeypatch):
    simulation = _simulation(status="created", user_id_owner=7)
    _patch_runtime_context_repositories(monkeypatch)

    async def fake_update_simulation(simulation_obj, simulation_in, session):
        simulation_obj.negotiation_state = simulation_in.negotiation_state.model_dump()
        simulation_obj.messages = [message.model_dump() for message in simulation_in.messages]
        simulation_obj.status = simulation_in.status
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )

    result = await simulations_service.start_simulation_srvc(
        simulation,
        SimulationStartRequest(side_a={"name": "Buyer", "role": "buyer"}),
        object(),
        _user(7),
    )

    assert result.negotiation_state.current_phase == "opening"
    assert result.negotiation_state.data["simulation_id"] == "10"
    assert "side_a" not in result.negotiation_state.data
    assert "side_b" not in result.negotiation_state.data
    assert simulation.negotiation_state["data"]["side_a"]["name"] == "Buyer"
    assert simulation.negotiation_state["data"]["side_b"] == {
        "persona_id": 300,
        "name": "Firm seller",
        "description": "Persona context",
    }
    assert simulation.negotiation_state["data"]["counterpart_persona"] == {
        "id": 300,
        "name": "Firm seller",
        "description": "Persona context",
    }


@pytest.mark.asyncio
async def test_start_simulation_separates_simulation_and_app_session_ids(monkeypatch):
    simulation = _simulation(status="created", session_id=44, user_id_owner=7)
    _patch_runtime_context_repositories(
        monkeypatch,
        app_session=SimpleNamespace(id=44, user_id=7),
    )

    async def fake_update_simulation(simulation_obj, simulation_in, session):
        simulation_obj.negotiation_state = simulation_in.negotiation_state.model_dump()
        simulation_obj.messages = [message.model_dump() for message in simulation_in.messages]
        simulation_obj.status = simulation_in.status
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )

    result = await simulations_service.start_simulation_srvc(
        simulation,
        SimulationStartRequest(side_a={"name": "Buyer"}, side_b={"name": "Seller"}),
        object(),
        _user(7),
    )

    assert result.negotiation_state.data["simulation_id"] == "10"
    assert "session_id" not in result.negotiation_state.data
    assert "app_session_id" not in result.negotiation_state.data
    assert simulation.negotiation_state["data"]["session_id"] == "10"
    assert simulation.negotiation_state["data"]["app_session_id"] == 44


@pytest.mark.asyncio
async def test_start_simulation_requires_existing_corpus(monkeypatch):
    simulation = _simulation(status="created", user_id_owner=7)
    _patch_runtime_context_repositories(monkeypatch, corpus=None)

    async def fake_get_corpus_by_id(corpus_id, session):
        return None

    monkeypatch.setattr(simulations_service.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)

    with pytest.raises(ValueError, match="Corpus not found"):
        await simulations_service.start_simulation_srvc(
            simulation,
            SimulationStartRequest(side_a={"name": "Buyer"}),
            object(),
            _user(7),
        )


@pytest.mark.asyncio
async def test_submit_turn_invokes_graph_and_persists_json_safe_response(monkeypatch):
    captured_state = []
    simulation = _simulation(
        status="active",
        user_id_owner=7,
        negotiation_state={
            "current_phase": "opening",
            "user_side": "side_a",
            "data": {
                "simulation_id": "10",
                "session_id": "10",
                "user_id": "7",
                "user_side": "side_a",
                "phase": "opening",
                "corpus_context": {"id": 200, "name": "Negotiation corpus"},
                "scenario_public_context": {"id": 100, "name": "Salary scenario"},
                "side_a_private_context": {"reservation": "SIDE-A-SECRET"},
                "side_b_private_context": {"reservation": "SIDE-B-SECRET"},
                "counterpart_persona_context": {"id": 300, "name": "Firm seller"},
                "messages": [],
                "event_log": [],
            },
        },
    )

    class FakeGraph:
        def invoke(self, state):
            captured_state.append(state)
            return {
                **state,
                "phase": "bargaining",
                "should_pause": True,
                "pause_reason": "counterpart_response_ready",
                "side_b_response": "I can move a little, but not that far.",
                "coach_advice": {"summary": "Hold near target."},
                "evaluation": {"next_best_action": "counter", "score": 0.6},
                "final_evaluation": {},
                "messages": [
                    *state["messages"],
                    {
                        "role": "assistant",
                        "content": "I can move a little, but not that far.",
                        "side": "side_b",
                    },
                ],
                "event_log": ["orchestrator:paused_for_user"],
            }

    async def fake_update_simulation(simulation_obj, simulation_in, session):
        simulation_obj.negotiation_state = simulation_in.negotiation_state.model_dump()
        simulation_obj.messages = [message.model_dump() for message in simulation_in.messages]
        simulation_obj.status = simulation_in.status
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )

    result = await simulations_service.submit_simulation_turn_srvc(
        simulation,
        SimulationTurnRequest(message="Could you do 95?"),
        object(),
        _user(7),
        FakeGraph(),
    )

    assert isinstance(result, SimulationTurnResponse)
    assert result.status == "paused"
    assert result.phase == "bargaining"
    assert result.should_pause is True
    assert result.pause_reason == "counterpart_response_ready"
    assert result.coach_advice == {"summary": "Hold near target."}
    assert not hasattr(result, "evaluation")
    assert result.final_evaluation == {}
    assert result.counterpart_response == "I can move a little, but not that far."
    assert captured_state[0]["simulation_id"] == "10"
    assert captured_state[0]["corpus_context"]["name"] == "Negotiation corpus"
    assert captured_state[0]["messages"][0]["content"] == "Could you do 95?"
    assert simulation.negotiation_state["data"]["evaluation"] == {
        "next_best_action": "counter",
        "score": 0.6,
    }
    assert "evaluation" not in result.model_dump()
    assert "event_log" not in result.model_dump()
    assert simulation.negotiation_state["data"]["counterpart_persona_context"]["name"] == "Firm seller"
    assert simulation.negotiation_state["data"]["phase"] == "bargaining"


@pytest.mark.asyncio
async def test_submit_turn_tags_human_provenance_and_disables_proxy_mode(monkeypatch):
    captured_state = []
    simulation = _simulation(
        status="paused",
        user_id_owner=7,
        negotiation_state={
            "current_phase": "bargaining",
            "user_side": "side_a",
            "data": {
                "simulation_id": "10",
                "session_id": "10",
                "user_id": "7",
                "user_side": "side_a",
                "phase": "bargaining",
                "auto_user_proxy_enabled": True,
                "user_proxy_persona_id": 300,
                "user_proxy_persona": {"id": 300, "name": "Firm seller"},
                "messages": [],
                "event_log": [],
            },
        },
    )

    class FakeGraph:
        def invoke(self, state):
            captured_state.append(state)
            return {
                **state,
                "phase": "bargaining",
                "should_pause": True,
                "pause_reason": "counterpart_response_ready",
                "messages": state["messages"],
            }

    async def fake_update_simulation(simulation_obj, simulation_in, session):
        simulation_obj.negotiation_state = simulation_in.negotiation_state.model_dump()
        simulation_obj.messages = [message.model_dump() for message in simulation_in.messages]
        simulation_obj.status = simulation_in.status
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )

    await simulations_service.submit_simulation_turn_srvc(
        simulation,
        SimulationTurnRequest(message="I want to revise the terms."),
        object(),
        _user(7),
        FakeGraph(),
    )

    assert captured_state[0]["messages"][0]["metadata"]["user_reply_origin"] == "user"
    assert captured_state[0]["auto_user_proxy_enabled"] is False
    assert captured_state[0]["user_proxy_persona"] == {}
    assert captured_state[0]["user_proxy_persona_id"] is None


@pytest.mark.asyncio
async def test_submit_proxy_turn_generates_message_and_persists_remainder_mode(monkeypatch):
    captured_state = []
    simulation = _simulation(
        status="paused",
        user_id_owner=7,
        negotiation_state={
            "current_phase": "bargaining",
            "user_side": "side_a",
            "data": {
                "simulation_id": "10",
                "session_id": "10",
                "user_id": "7",
                "user_side": "side_a",
                "phase": "bargaining",
                "scenario_public_context": {"id": 100, "name": "Salary scenario"},
                "side_a_private_context": {"reservation": "SIDE-A-SECRET"},
                "side_b_private_context": {"reservation": "SIDE-B-SECRET"},
                "coach_advice": {"suggested_response": "Ask for 100 and hold firm."},
                "messages": [],
                "event_log": [],
            },
        },
    )

    class FakeGraph:
        def invoke(self, state):
            captured_state.append(state)
            return {
                **state,
                "phase": "bargaining",
                "should_pause": True,
                "pause_reason": "counterpart_response_ready",
                "side_b_response": "I can do 98.",
                "messages": [
                    *state["messages"],
                    {
                        "role": "assistant",
                        "content": "I can do 98.",
                        "side": "side_b",
                    },
                ],
            }

    async def fake_update_simulation(simulation_obj, simulation_in, session):
        simulation_obj.negotiation_state = simulation_in.negotiation_state.model_dump()
        simulation_obj.messages = [message.model_dump() for message in simulation_in.messages]
        simulation_obj.status = simulation_in.status
        return simulation_obj

    async def fake_invoke_proxy_turn(state, persona, duration):
        assert state["coach_advice"]["suggested_response"] == "Ask for 100 and hold firm."
        assert persona.id == 300
        assert duration == "remainder"
        return {
            "message": "I can move to 100 if we can settle today.",
            "event_log": ["proxy:completed"],
        }

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )
    monkeypatch.setattr(
        simulations_service,
        "invoke_user_proxy_turn",
        fake_invoke_proxy_turn,
    )
    _patch_runtime_context_repositories(monkeypatch)

    result = await simulations_service.submit_simulation_proxy_turn_srvc(
        simulation,
        SimulationProxyTurnRequest(persona_id=300, duration="remainder"),
        object(),
        _user(7),
        FakeGraph(),
    )

    assert isinstance(result, SimulationProxyTurnResponse)
    assert result.proxy_response == "I can move to 100 if we can settle today."
    assert result.auto_user_proxy_enabled is True
    assert result.user_proxy_persona["name"] == "Firm seller"
    assert captured_state[0]["messages"][0]["content"] == "I can move to 100 if we can settle today."
    assert captured_state[0]["messages"][0]["metadata"]["user_reply_origin"] == "auto_user_proxy"
    assert captured_state[0]["messages"][0]["metadata"]["persona_id"] == 300
    assert simulation.negotiation_state["data"]["auto_user_proxy_enabled"] is True


@pytest.mark.asyncio
async def test_submit_proxy_turn_preserves_remainder_mode_when_graph_omits_proxy_fields(monkeypatch):
    simulation = _simulation(
        status="paused",
        user_id_owner=7,
        negotiation_state={
            "current_phase": "bargaining",
            "user_side": "side_a",
            "data": {
                "simulation_id": "10",
                "session_id": "10",
                "user_id": "7",
                "user_side": "side_a",
                "phase": "bargaining",
                "scenario_public_context": {"id": 100, "name": "Salary scenario"},
                "side_a_private_context": {"reservation": "SIDE-A-SECRET"},
                "side_b_private_context": {"reservation": "SIDE-B-SECRET"},
                "coach_advice": {"suggested_response": "Ask for 100 and hold firm."},
                "messages": [],
                "event_log": [],
            },
        },
    )

    class FakeGraph:
        def invoke(self, state):
            return {
                "simulation_id": state["simulation_id"],
                "session_id": state["session_id"],
                "user_id": state["user_id"],
                "user_side": state["user_side"],
                "phase": "bargaining",
                "should_pause": True,
                "pause_reason": "counterpart_response_ready",
                "side_b_response": "I can do 98.",
                "messages": [
                    *state["messages"],
                    {
                        "role": "assistant",
                        "content": "I can do 98.",
                        "side": "side_b",
                    },
                ],
            }

    async def fake_update_simulation(simulation_obj, simulation_in, session):
        simulation_obj.negotiation_state = simulation_in.negotiation_state.model_dump()
        simulation_obj.messages = [message.model_dump() for message in simulation_in.messages]
        simulation_obj.status = simulation_in.status
        return simulation_obj

    async def fake_invoke_proxy_turn(state, persona, duration):
        assert duration == "remainder"
        return {
            "message": "I can move to 100 if we can settle today.",
            "event_log": ["proxy:completed"],
        }

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )
    monkeypatch.setattr(
        simulations_service,
        "invoke_user_proxy_turn",
        fake_invoke_proxy_turn,
    )
    _patch_runtime_context_repositories(monkeypatch)

    result = await simulations_service.submit_simulation_proxy_turn_srvc(
        simulation,
        SimulationProxyTurnRequest(persona_id=300, duration="remainder"),
        object(),
        _user(7),
        FakeGraph(),
    )

    assert result.auto_user_proxy_enabled is True
    assert result.user_proxy_persona["name"] == "Firm seller"
    assert simulation.negotiation_state["data"]["auto_user_proxy_enabled"] is True
    assert simulation.negotiation_state["data"]["user_proxy_persona"]["name"] == "Firm seller"
    assert simulation.negotiation_state["data"]["user_proxy_persona_id"] == 300


@pytest.mark.asyncio
async def test_submit_proxy_turn_rejects_missing_persona(monkeypatch):
    simulation = _simulation(
        status="paused",
        user_id_owner=7,
        negotiation_state={
            "current_phase": "bargaining",
            "user_side": "side_a",
            "data": {
                "simulation_id": "10",
                "session_id": "10",
                "user_id": "7",
                "user_side": "side_a",
                "phase": "bargaining",
                "messages": [],
                "event_log": [],
            },
        },
    )
    _patch_runtime_context_repositories(monkeypatch)

    async def fake_get_counterpart_persona_by_id(persona_id, session):
        return None

    monkeypatch.setattr(
        simulations_service.counterpart_personas_repo,
        "get_counterpart_persona_by_id",
        fake_get_counterpart_persona_by_id,
    )

    with pytest.raises(ValueError, match="Counterpart persona not found"):
        await simulations_service.submit_simulation_proxy_turn_srvc(
            simulation,
            SimulationProxyTurnRequest(persona_id=999, duration="this_turn"),
            object(),
            _user(7),
            object(),
        )


@pytest.mark.asyncio
async def test_disable_proxy_mode_clears_state_without_adding_turn(monkeypatch):
    simulation = _simulation(
        status="paused",
        user_id_owner=7,
        negotiation_state={
            "current_phase": "bargaining",
            "user_side": "side_a",
            "data": {
                "simulation_id": "10",
                "session_id": "10",
                "user_id": "7",
                "user_side": "side_a",
                "phase": "bargaining",
                "auto_user_proxy_enabled": True,
                "user_proxy_persona_id": 300,
                "user_proxy_persona": {"id": 300, "name": "Firm seller"},
                "messages": [{"role": "user", "content": "Existing", "metadata": {}}],
                "event_log": [],
            },
        },
        messages=[{"role": "user", "content": "Existing", "metadata": {}}],
    )

    async def fake_update_simulation(simulation_obj, simulation_in, session):
        simulation_obj.negotiation_state = simulation_in.negotiation_state.model_dump()
        simulation_obj.messages = [message.model_dump() for message in simulation_in.messages]
        simulation_obj.status = simulation_in.status
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )

    result = await simulations_service.disable_simulation_proxy_srvc(
        simulation,
        object(),
        _user(7),
    )

    assert isinstance(result, SimulationProxyDisableResponse)
    assert result.auto_user_proxy_enabled is False
    assert result.messages[0].content == "Existing"
    assert simulation.negotiation_state["data"]["auto_user_proxy_enabled"] is False


@pytest.mark.asyncio
async def test_submit_turn_backfills_simulation_id_from_legacy_session_id(monkeypatch):
    captured_state = []
    simulation = _simulation(
        status="active",
        user_id_owner=7,
        negotiation_state={
            "current_phase": "opening",
            "user_side": "side_a",
            "data": {
                "session_id": "10",
                "user_id": "7",
                "user_side": "side_a",
                "phase": "opening",
                "messages": [],
                "event_log": [],
            },
        },
    )

    class FakeGraph:
        def invoke(self, state):
            captured_state.append(state)
            return state

    async def fake_update_simulation(simulation_obj, simulation_in, session):
        simulation_obj.negotiation_state = simulation_in.negotiation_state.model_dump()
        simulation_obj.messages = [message.model_dump() for message in simulation_in.messages]
        simulation_obj.status = simulation_in.status
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )

    await simulations_service.submit_simulation_turn_srvc(
        simulation,
        SimulationTurnRequest(message="Could you do 95?"),
        object(),
        _user(7),
        FakeGraph(),
    )

    assert captured_state[0]["simulation_id"] == "10"
    assert captured_state[0]["session_id"] == "10"


@pytest.mark.asyncio
async def test_submit_end_action_returns_final_evaluation(monkeypatch):
    simulation = _simulation(
        status="paused",
        user_id_owner=7,
        negotiation_state={
            "current_phase": "bargaining",
            "user_side": "side_a",
            "data": {
                "simulation_id": "10",
                "session_id": "10",
                "user_id": "7",
                "user_side": "side_a",
                "phase": "bargaining",
                "messages": [],
                "event_log": [],
            },
        },
    )

    class FakeGraph:
        def invoke(self, state):
            assert state["requested_action"] == "end"
            return {
                **state,
                "phase": "ended",
                "should_pause": False,
                "pause_reason": "",
                "terminal_reason": "student_request",
                "final_evaluation": {
                    "evaluated_side": "side_a",
                    "overall_score": 0.8,
                    "reasoning": "Strong overall performance.",
                    "confidence": "high",
                },
            }

    async def fake_update_simulation(simulation_obj, simulation_in, session):
        simulation_obj.negotiation_state = simulation_in.negotiation_state.model_dump()
        simulation_obj.messages = [message.model_dump() for message in simulation_in.messages]
        simulation_obj.status = simulation_in.status
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )

    result = await simulations_service.submit_simulation_turn_srvc(
        simulation,
        SimulationTurnRequest(message="End the simulation.", action="end"),
        object(),
        _user(7),
        FakeGraph(),
    )

    assert result.status == "completed"
    assert result.should_pause is False
    assert result.final_evaluation["overall_score"] == 0.8


@pytest.mark.asyncio
async def test_submit_turn_without_structured_end_cannot_report_student_request(monkeypatch):
    simulation = _simulation(
        status="active",
        user_id_owner=7,
        negotiation_state={
            "current_phase": "bargaining",
            "user_side": "side_a",
            "data": {
                "simulation_id": "10",
                "session_id": "10",
                "user_id": "7",
                "user_side": "side_a",
                "phase": "bargaining",
                "messages": [],
                "event_log": [],
            },
        },
    )
    captured_state = []

    class FakeGraph:
        def invoke(self, state):
            captured_state.append(state)
            return {
                **state,
                "phase": "ended",
                "should_pause": False,
                "pause_reason": "",
                "terminal_reason": "classified_intent",
                "intent_classification": {
                    "intent": "end",
                    "confidence": "high",
                    "reasoning": "Explicit stop request.",
                },
                "final_evaluation": {
                    "evaluated_side": "side_a",
                    "overall_score": 0.5,
                    "reasoning": "Ended on request.",
                    "confidence": "medium",
                },
            }

    async def fake_update_simulation(simulation_obj, simulation_in, session):
        simulation_obj.negotiation_state = simulation_in.negotiation_state.model_dump()
        simulation_obj.messages = [message.model_dump() for message in simulation_in.messages]
        simulation_obj.status = simulation_in.status
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )

    result = await simulations_service.submit_simulation_turn_srvc(
        simulation,
        SimulationTurnRequest(message="Please end the simulation now."),
        object(),
        _user(7),
        FakeGraph(),
    )

    assert "requested_action" not in captured_state[0]
    assert result.status == "completed"
    assert simulation.negotiation_state["data"]["terminal_reason"] == "classified_intent"


@pytest.mark.asyncio
async def test_submit_turn_acceptance_preflags_requested_end(monkeypatch):
    simulation = _simulation(
        status="active",
        user_id_owner=7,
        negotiation_state={
            "current_phase": "bargaining",
            "user_side": "side_a",
            "data": {
                "simulation_id": "10",
                "session_id": "10",
                "user_id": "7",
                "user_side": "side_a",
                "phase": "bargaining",
                "messages": [],
                "event_log": [],
            },
        },
    )

    class FakeGraph:
        def invoke(self, state):
            assert state["requested_action"] == "end"
            return {
                **state,
                "phase": "ended",
                "should_pause": False,
                "pause_reason": "",
                "terminal_reason": "student_request",
                "final_evaluation": {
                    "evaluated_side": "side_a",
                    "overall_score": 0.9,
                    "reasoning": "Deal accepted.",
                    "confidence": "high",
                },
            }

    async def fake_update_simulation(simulation_obj, simulation_in, session):
        simulation_obj.negotiation_state = simulation_in.negotiation_state.model_dump()
        simulation_obj.messages = [message.model_dump() for message in simulation_in.messages]
        simulation_obj.status = simulation_in.status
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )

    result = await simulations_service.submit_simulation_turn_srvc(
        simulation,
        SimulationTurnRequest(message="I agree to your terms."),
        object(),
        _user(7),
        FakeGraph(),
    )

    assert result.status == "completed"
    assert result.phase == "ended"
    assert result.should_pause is False


@pytest.mark.asyncio
async def test_submit_turn_terminal_response_does_not_reuse_old_counterpart_message(monkeypatch):
    simulation = _simulation(
        status="paused",
        user_id_owner=7,
        user_side="side_a",
        negotiation_state={
            "current_phase": "bargaining",
            "user_side": "side_a",
            "data": {
                "simulation_id": "10",
                "session_id": "10",
                "user_id": "7",
                "user_side": "side_a",
                "phase": "bargaining",
                "side_b_response": "Earlier counterpart message.",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "Earlier counterpart message.",
                        "side": "side_b",
                    }
                ],
                "event_log": [],
            },
        },
    )

    class FakeGraph:
        def invoke(self, state):
            return {
                **state,
                "phase": "ended",
                "should_pause": False,
                "pause_reason": "",
                "terminal_reason": "student_request",
                "final_evaluation": {
                    "evaluated_side": "side_a",
                    "overall_score": 0.9,
                    "reasoning": "Finished cleanly.",
                    "confidence": "high",
                },
            }

    async def fake_update_simulation(simulation_obj, simulation_in, session):
        simulation_obj.negotiation_state = simulation_in.negotiation_state.model_dump()
        simulation_obj.messages = [message.model_dump() for message in simulation_in.messages]
        simulation_obj.status = simulation_in.status
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )

    result = await simulations_service.submit_simulation_turn_srvc(
        simulation,
        SimulationTurnRequest(message="I agree to your terms."),
        object(),
        _user(7),
        FakeGraph(),
    )

    assert result.status == "completed"
    assert result.counterpart_response is None


@pytest.mark.asyncio
async def test_submit_turn_rejects_terminal_phase_even_if_status_is_paused(monkeypatch):
    simulation = _simulation(
        status="paused",
        negotiation_state={
            "current_phase": "ended",
            "user_side": "side_a",
            "data": {
                "simulation_id": "10",
                "session_id": "10",
                "user_id": "7",
                "user_side": "side_a",
                "phase": "ended",
                "messages": [],
                "event_log": [],
            },
        },
    )

    with pytest.raises(ValueError, match="Ended simulations cannot accept additional turns"):
        await simulations_service.submit_simulation_turn_srvc(
            simulation,
            SimulationTurnRequest(message="One more message."),
            object(),
            _user(7),
            object(),
        )


@pytest.mark.asyncio
async def test_get_simulation_state_redacts_internal_negotiation_secrets():
    simulation = _simulation(
        status="active",
        negotiation_state={
            "current_phase": "bargaining",
            "user_side": "side_b",
            "data": _internal_state_with_secrets(),
        },
    )

    result = await simulations_service.get_simulation_state_srvc(simulation)
    serialized = repr(result.negotiation_state.data)

    assert "PUBLIC" in serialized
    assert "SIDE_A_SECRET" not in serialized
    assert "ROLLING_EVALUATION_SECRET" not in serialized
    assert "INTERNAL_EVENT" not in serialized


@pytest.mark.asyncio
async def test_negotiation_graph_is_cached_per_corpus_index(monkeypatch):
    simulations_service.NEGOTIATION_GRAPH_CACHE.clear()
    build_calls = []
    simulation = _simulation(
        status="active",
        corpus_index_id=77,
        coach_prompt_id=11,
        counterpart_prompt_id=12,
        evaluator_prompt_id=13,
    )

    async def fake_get_corpus_index_by_id(corpus_index_id, session):
        return SimpleNamespace(
            id=corpus_index_id,
            corpus_id=200,
            vector_store_id=12,
            status="built",
            embedding_model="mini-l6-v2",
            embedding_dimensions=384,
            vector_namespace="corpus-index-77",
        )

    async def fake_get_vector_store_by_id(vector_store_id, session):
        return SimpleNamespace(
            id=vector_store_id,
            backend="chroma",
            collection_name="negotiation",
            path="./chroma_db",
            table_name=None,
        )

    async def fake_get_prompt_by_id(prompt_id, session):
        prompts = {
            11: SimpleNamespace(id=11, messages={"template": "DB coach {phase}"}),
            12: SimpleNamespace(id=12, messages={"template": "DB counterpart {phase}"}),
            13: SimpleNamespace(id=13, messages={"template": "DB evaluator {phase}"}),
        }
        return prompts[prompt_id]

    def fake_choose_embedding_model(model_name):
        return object(), {"dimensionality": 384}

    def fake_instantiate_chroma_vector_store(**kwargs):
        return SimpleNamespace(as_retriever=lambda search_kwargs: ("retriever", search_kwargs))

    async def fake_get_rag_profile_by_id(profile_id, session):
        return SimpleNamespace(
            id=profile_id,
            strategy="crag",
            config={
                "top_k": 6,
                "reranker": "none",
                "top_n": 6,
                "max_rewrite_attempts": 0,
            },
        )

    def fake_make_dense_retriever(vector_store, k=4, metadata_filter=None):
        assert k == 6
        assert metadata_filter == {"corpus_index_id": 77}
        return ("dense", metadata_filter)

    def fake_make_crag_graph(retriever, rag_profile):
        return ("crag", retriever, rag_profile.id, rag_profile.config["reranker"])

    def fake_make_negotiation_graph(
        crag_graph=None,
        coach_prompt_template=None,
        counterpart_prompt_template=None,
        evaluator_prompt_template=None,
        intent_classifier_model=None,
    ):
        build_calls.append(
            (
                crag_graph,
                coach_prompt_template,
                counterpart_prompt_template,
                evaluator_prompt_template,
                intent_classifier_model,
            )
        )
        return SimpleNamespace(invoke=lambda state: state)

    monkeypatch.setattr(
        simulations_service.corpus_indices_repo,
        "get_corpus_index_by_id",
        fake_get_corpus_index_by_id,
    )
    monkeypatch.setattr(
        simulations_service.vector_stores_repo,
        "get_vector_store_by_id",
        fake_get_vector_store_by_id,
    )
    monkeypatch.setattr(
        simulations_service.prompts_repo,
        "get_prompt_by_id",
        fake_get_prompt_by_id,
    )
    monkeypatch.setattr(
        simulations_service.rag_profiles_repo,
        "get_rag_profile_by_id",
        fake_get_rag_profile_by_id,
    )
    monkeypatch.setattr(simulations_service, "choose_embedding_model", fake_choose_embedding_model)
    monkeypatch.setattr(
        simulations_service,
        "instantiate_chroma_vector_store",
        fake_instantiate_chroma_vector_store,
    )
    monkeypatch.setattr(simulations_service, "make_dense_retriever", fake_make_dense_retriever)
    monkeypatch.setattr(simulations_service, "_make_crag_graph", fake_make_crag_graph)
    monkeypatch.setattr(
        simulations_service,
        "make_negotiation_graph",
        fake_make_negotiation_graph,
    )

    first = await simulations_service._get_negotiation_graph_for_simulation(simulation, object())
    second = await simulations_service._get_negotiation_graph_for_simulation(simulation, object())

    assert first is second
    assert len(build_calls) == 1
    assert build_calls[0][0] == ("crag", ("dense", {"corpus_index_id": 77}), 500, "none")
    assert build_calls[0][1:] == (
        "DB coach {phase}",
        "DB counterpart {phase}",
        "DB evaluator {phase}",
        None,
    )


@pytest.mark.asyncio
async def test_cancel_simulation_uses_status_transition(monkeypatch):
    captured = []
    simulation = _simulation(status="paused")

    async def fake_update_status(simulation_obj, status_in, session):
        captured.append(status_in.status)
        simulation_obj.status = status_in.status
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation_status",
        fake_update_status,
    )

    result = await simulations_service.cancel_simulation_srvc(simulation, object())

    assert result.status == "cancelled"
    assert captured == ["cancelled"]


@pytest.mark.asyncio
async def test_review_simulation_stamps_current_teacher(monkeypatch):
    captured = []
    simulation = _simulation(status="completed")

    async def fake_review_simulation(simulation_obj, review_in, session):
        captured.append(review_in)
        simulation_obj.teacher_id = review_in.teacher_id
        simulation_obj.teacher_feedback = review_in.teacher_feedback
        simulation_obj.teacher_reviewed = review_in.teacher_reviewed
        simulation_obj.reviewed_at = datetime.now(timezone.utc)
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "review_simulation",
        fake_review_simulation,
    )

    result = await simulations_service.review_simulation_srvc(
        simulation,
        SimulationTeacherReviewRequest(teacher_feedback="Strong reflection on BATNA."),
        object(),
        _user(55),
    )

    assert result.teacher_reviewed is True
    assert result.teacher_id == 55
    assert result.teacher_feedback == "Strong reflection on BATNA."
    assert captured[0].teacher_id == 55
    assert captured[0].teacher_feedback == "Strong reflection on BATNA."


@pytest.mark.asyncio
async def test_list_completed_simulations_includes_all_completed_for_teacher(monkeypatch):
    rows = [
        _simulation(1, status="completed", user_id_owner=40, user_id_participant=41, scenario_id=101),
        _simulation(2, status="completed", user_id_owner=42, user_id_participant=None, scenario_id=102),
    ]
    rows[0].last_updated = datetime(2026, 1, 2, tzinfo=timezone.utc)
    rows[1].last_updated = datetime(2026, 1, 1, tzinfo=timezone.utc)

    async def fake_list_completed_simulations(session, *, skip, limit, teacher_id):
        assert skip == 0
        assert limit == 20
        assert teacher_id == 7
        return rows, False

    async def fake_get_scenario_name(scenario_id, session):
        return {101: "Salary", 102: "Vendor"}[scenario_id]

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "list_completed_simulations",
        fake_list_completed_simulations,
    )
    monkeypatch.setattr(
        simulations_service,
        "_get_scenario_name",
        fake_get_scenario_name,
    )

    result = await simulations_service.list_completed_simulations_srvc(
        object(),
        current_user=_user(7),
        skip=0,
        limit=20,
    )

    assert result.skip == 0
    assert result.limit == 20
    assert result.has_more is False
    assert [item.id for item in result.items] == [1, 2]
    assert result.items[0].scenario_name == "Salary"
    assert result.items[0].participant_user_id == 41
    assert result.items[1].participant_user_id == 42


@pytest.mark.asyncio
async def test_list_reviews_scopes_to_current_teacher(monkeypatch):
    rows = [
        _review_row(1, teacher_id=7, scenario_id=101, teacher_feedback="First"),
        _review_row(2, teacher_id=7, scenario_id=102, teacher_feedback="Second"),
    ]

    async def fake_list_reviewed_simulations(session, *, skip, limit, teacher_id):
        assert skip == 5
        assert limit == 10
        assert teacher_id == 7
        return rows, True

    async def fake_get_scenario_name(scenario_id, session):
        return {101: "Salary", 102: "Vendor"}[scenario_id]

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "list_reviewed_simulations",
        fake_list_reviewed_simulations,
    )
    monkeypatch.setattr(
        simulations_service,
        "_get_scenario_name",
        fake_get_scenario_name,
    )

    result = await simulations_service.list_reviewed_simulations_srvc(
        object(),
        current_user=_user(7),
        skip=5,
        limit=10,
    )

    assert result.skip == 5
    assert result.limit == 10
    assert result.has_more is True
    assert [item.id for item in result.items] == [1, 2]
    assert result.items[0].teacher_feedback == "First"
    assert result.items[1].scenario_name == "Vendor"


@pytest.mark.asyncio
async def test_update_review_simulation_requires_author_or_admin(monkeypatch):
    simulation = _review_row(10, teacher_id=11, teacher_feedback="Initial")

    with pytest.raises(ValueError, match="Only the review author or an admin can modify this review"):
        await simulations_service.update_review_simulation_srvc(
            simulation,
            SimulationTeacherReviewRequest(teacher_feedback="Updated"),
            object(),
            _user(55),
        )


@pytest.mark.asyncio
async def test_update_review_simulation_allows_admin_and_refreshes_timestamp(monkeypatch):
    captured = []
    simulation = _review_row(10, teacher_id=11, teacher_feedback="Initial")

    async def fake_update_review(simulation_obj, review_in, session):
        captured.append(review_in)
        simulation_obj.teacher_feedback = review_in.teacher_feedback
        simulation_obj.reviewed_at = review_in.reviewed_at
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_review_simulation",
        fake_update_review,
    )

    result = await simulations_service.update_review_simulation_srvc(
        simulation,
        SimulationTeacherReviewRequest(teacher_feedback="  Updated insight  "),
        object(),
        _admin(99),
    )

    assert result.teacher_feedback == "Updated insight"
    assert captured[0].teacher_feedback == "Updated insight"
    assert captured[0].reviewed_at is not None


@pytest.mark.asyncio
async def test_delete_review_simulation_clears_review_fields(monkeypatch):
    captured = []
    simulation = _review_row(10, teacher_id=11, teacher_feedback="Initial")

    async def fake_delete_review(simulation_obj, session):
        captured.append(simulation_obj.id)
        simulation_obj.teacher_id = None
        simulation_obj.teacher_feedback = None
        simulation_obj.teacher_reviewed = False
        simulation_obj.reviewed_at = None
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "delete_review_simulation",
        fake_delete_review,
    )

    result = await simulations_service.delete_review_simulation_srvc(
        simulation,
        object(),
        _admin(77),
    )

    assert result.teacher_reviewed is False
    assert result.teacher_id is None
    assert result.teacher_feedback is None
    assert result.reviewed_at is None
    assert captured == [10]
