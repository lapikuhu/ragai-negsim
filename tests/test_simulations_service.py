from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.schemas.simulations_schemas import (
    SimulationCreate,
    SimulationCreateRequest,
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
        scenario = SimpleNamespace(id=100, name="Salary scenario", description="Scenario context")
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

    with pytest.raises(ValueError, match="Coach prompt not found"):
        await simulations_service.create_simulation_srvc(
            SimulationCreateRequest(
                name="Salary negotiation",
                corpus_id=200,
                corpus_index_id=77,
                coach_prompt_id=11,
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

    assert captured == [(5, 10, "active", 3, 4, None, 200, 77, 11, 12, 13, 8, 100)]
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
            opening_message="I would like to discuss the price.",
        ),
        object(),
        _user(7),
    )

    assert isinstance(result, SimulationReadWithState)
    assert result.status == "active"
    assert result.negotiation_state.user_side == "side_a"
    assert result.negotiation_state.current_phase == "opening"
    assert result.negotiation_state.data["side_a"]["name"] == "Buyer"
    assert result.negotiation_state.data["side_b"]["name"] == "Seller"
    assert result.negotiation_state.data["corpus_context"] == {
        "id": 200,
        "name": "Negotiation corpus",
        "description": "Corpus context",
    }
    assert result.negotiation_state.data["corpus_index_context"]["id"] == 77
    assert result.negotiation_state.data["corpus_index_context"]["name"] == "Negotiation index"
    assert result.negotiation_state.data["coach_prompt_context"]["name"] == "Coach prompt"
    assert result.negotiation_state.data["counterpart_prompt_context"]["name"] == "Counterpart prompt"
    assert result.negotiation_state.data["evaluator_prompt_context"]["name"] == "Evaluator prompt"
    assert result.negotiation_state.data["scenario_context"]["name"] == "Salary scenario"
    assert result.negotiation_state.data["counterpart_persona_context"]["name"] == "Firm seller"
    assert result.messages[0].content == "I would like to discuss the price."
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
    assert result.negotiation_state.data["side_a"]["name"] == "Buyer"
    assert result.negotiation_state.data["side_b"] == {
        "persona_id": 300,
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
    assert result.negotiation_state.data["session_id"] == "10"
    assert result.negotiation_state.data["app_session_id"] == 44


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
                "scenario_context": {"id": 100, "name": "Salary scenario"},
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
    assert result.counterpart_response == "I can move a little, but not that far."
    assert captured_state[0]["simulation_id"] == "10"
    assert captured_state[0]["corpus_context"]["name"] == "Negotiation corpus"
    assert captured_state[0]["messages"][0]["content"] == "Could you do 95?"
    assert simulation.negotiation_state["data"]["counterpart_persona_context"]["name"] == "Firm seller"
    assert simulation.negotiation_state["data"]["phase"] == "bargaining"


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

    def fake_make_dense_retriever(vector_store, k=4, metadata_filter=None):
        assert metadata_filter == {"corpus_index_id": 77}
        return ("dense", metadata_filter)

    def fake_make_crag_graph(retriever):
        return ("crag", retriever)

    def fake_make_negotiation_graph(
        crag_graph=None,
        coach_prompt_template=None,
        counterpart_prompt_template=None,
        evaluator_prompt_template=None,
    ):
        build_calls.append(
            (
                crag_graph,
                coach_prompt_template,
                counterpart_prompt_template,
                evaluator_prompt_template,
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
    assert build_calls[0][1:] == (
        "DB coach {phase}",
        "DB counterpart {phase}",
        "DB evaluator {phase}",
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
