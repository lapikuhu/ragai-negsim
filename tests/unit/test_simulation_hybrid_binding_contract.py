from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from app.schemas.simulations_schemas import (
    SimulationCreate,
    SimulationCreateRequest,
    SimulationRead,
    SimulationUpdate,
    SimulationUpdateRequest,
)
from app.services import simulations_service
from app.web.routes.simulations_route import router as simulations_router


def _crag_profile(weight: float) -> SimpleNamespace:
    return SimpleNamespace(id=7, strategy="crag", config={"bm25_weight": weight})


def _simulation(*, corpus_index_id: int | None, bm25_index_id: int | None):
    timestamp = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=11,
        name="Binding contract",
        description=None,
        status="created",
        session_id=None,
        user_id_owner=1,
        user_id_participant=None,
        scenario_id=None,
        corpus_id=44,
        corpus_index_id=corpus_index_id,
        bm25_index_id=bm25_index_id,
        rag_profile_id=7,
        coach_prompt_id=None,
        counterpart_prompt_id=None,
        evaluator_prompt_id=None,
        counter_part_side_persona_id=None,
        user_side=None,
        teacher_reviewed=False,
        teacher_id=None,
        teacher_feedback=None,
        reviewed_at=None,
        created_at=timestamp,
        last_updated=timestamp,
        bm25_artifact=b"must never be serialized",
        compressed_artifact_data=b"must never be serialized",
    )


@pytest.fixture
def explicit_binding_dependencies(monkeypatch):
    calls = {"dense": [], "bm25": []}

    async def get_dense(corpus_id, corpus_index_id, session):
        calls["dense"].append((corpus_id, corpus_index_id))
        return SimpleNamespace(
            id=corpus_index_id,
            corpus_id=corpus_id,
            chunking_profile_id=9,
        )

    async def get_bm25(corpus_id, bm25_index_id, session):
        calls["bm25"].append((corpus_id, bm25_index_id))
        return SimpleNamespace(
            id=bm25_index_id,
            corpus_id=corpus_id,
            chunking_profile_id=9,
            document_count=2,
            document_chunk_ids_checksum="chunk-snapshot",
        )

    async def get_chunk_ids(corpus_index_id, session):
        return [71, 72]

    monkeypatch.setattr(simulations_service, "_get_valid_built_corpus_index", get_dense)
    monkeypatch.setattr(simulations_service, "_get_valid_built_bm25_index", get_bm25)
    monkeypatch.setattr(
        simulations_service.indexed_chunks_repo,
        "get_document_chunk_ids_by_corpus_index_id",
        get_chunk_ids,
    )
    monkeypatch.setattr(
        simulations_service.corpus_bm25_indices_repo,
        "document_chunk_ids_checksum",
        lambda chunk_ids: "chunk-snapshot",
    )
    return calls


def test_simulation_api_schemas_expose_only_nullable_binding_ids():
    schemas = (
        SimulationCreateRequest,
        SimulationCreate,
        SimulationUpdateRequest,
        SimulationUpdate,
        SimulationRead,
    )

    for schema in schemas:
        fields = schema.model_fields
        assert "corpus_index_id" in fields
        assert "bm25_index_id" in fields
        assert not any("artifact" in name.lower() for name in fields)

    app = FastAPI()
    app.include_router(simulations_router)
    components = app.openapi()["components"]["schemas"]
    for schema_name in (
        "SimulationCreateRequest",
        "SimulationUpdateRequest",
        "SimulationRead",
        "SimulationReadWithState",
    ):
        properties = components[schema_name]["properties"]
        assert {"corpus_index_id", "bm25_index_id"} <= set(properties)
        assert not any("artifact" in name.lower() for name in properties)


def test_read_schema_preserves_selected_ids_without_artifact_payloads():
    read = simulations_service._read_simulation(
        _simulation(corpus_index_id=None, bm25_index_id=202)
    )

    payload = read.model_dump()

    assert payload["corpus_index_id"] is None
    assert payload["bm25_index_id"] == 202
    assert not {"artifact", "bm25_artifact", "compressed_artifact_data"} & set(payload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("weight", "corpus_index_id", "bm25_index_id", "required_message"),
    [
        (0.0, None, None, "dense corpus index selection"),
        (1.0, None, None, "BM25 index selection"),
        (0.5, None, 202, "dense corpus index selection"),
        (0.5, 101, None, "BM25 index selection"),
    ],
)
async def test_create_requires_the_binding_selected_by_bm25_weight(
    monkeypatch,
    explicit_binding_dependencies,
    weight,
    corpus_index_id,
    bm25_index_id,
    required_message,
):
    async def get_profile(profile_id, session):
        return _crag_profile(weight)

    monkeypatch.setattr(
        simulations_service.rag_profiles_repo,
        "get_rag_profile_by_id",
        get_profile,
    )

    with pytest.raises(ValueError, match=required_message):
        await simulations_service.create_simulation_srvc(
            SimulationCreateRequest(
                name="Create binding validation",
                corpus_id=44,
                corpus_index_id=corpus_index_id,
                bm25_index_id=bm25_index_id,
                rag_profile_id=7,
            ),
            object(),
            SimpleNamespace(id=1),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("weight", "corpus_index_id", "bm25_index_id"),
    [(0.0, 101, None), (1.0, None, 202), (0.5, 101, 202)],
)
async def test_create_persists_only_explicit_weight_compatible_bindings(
    monkeypatch,
    explicit_binding_dependencies,
    weight,
    corpus_index_id,
    bm25_index_id,
):
    persisted = []

    async def get_profile(profile_id, session):
        return _crag_profile(weight)

    async def get_prompt_template(prompt_id, role, session):
        return None

    async def create_simulation(simulation_in, session):
        persisted.append(simulation_in)
        return simulation_in

    monkeypatch.setattr(
        simulations_service.rag_profiles_repo,
        "get_rag_profile_by_id",
        get_profile,
    )
    monkeypatch.setattr(simulations_service, "_get_prompt_template", get_prompt_template)
    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "create_simulation",
        create_simulation,
    )
    monkeypatch.setattr(simulations_service, "_read_simulation", lambda value: value)

    result = await simulations_service.create_simulation_srvc(
        SimulationCreateRequest(
            name="Explicit create binding",
            corpus_id=44,
            corpus_index_id=corpus_index_id,
            bm25_index_id=bm25_index_id,
            rag_profile_id=7,
        ),
        object(),
        SimpleNamespace(id=1),
    )

    assert result is persisted[0]
    assert persisted[0].corpus_index_id == corpus_index_id
    assert persisted[0].bm25_index_id == bm25_index_id
    assert explicit_binding_dependencies["dense"] == (
        [] if corpus_index_id is None else [(44, corpus_index_id)]
    )
    assert explicit_binding_dependencies["bm25"] == (
        [] if bm25_index_id is None else [(44, bm25_index_id)]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("weight", "existing_dense", "existing_bm25", "update", "required_message"),
    [
        (0.0, 101, None, SimulationUpdateRequest(corpus_index_id=None), "dense corpus index selection"),
        (1.0, None, 202, SimulationUpdateRequest(bm25_index_id=None), "BM25 index selection"),
        (0.5, 101, 202, SimulationUpdateRequest(corpus_index_id=None), "dense corpus index selection"),
        (0.5, 101, 202, SimulationUpdateRequest(bm25_index_id=None), "BM25 index selection"),
    ],
)
async def test_update_rejects_clearing_a_weight_required_binding(
    monkeypatch,
    explicit_binding_dependencies,
    weight,
    existing_dense,
    existing_bm25,
    update,
    required_message,
):
    async def get_profile(profile_id, session):
        return _crag_profile(weight)

    monkeypatch.setattr(
        simulations_service.rag_profiles_repo,
        "get_rag_profile_by_id",
        get_profile,
    )

    with pytest.raises(ValueError, match=required_message):
        await simulations_service.update_simulation_srvc(
            _simulation(
                corpus_index_id=existing_dense,
                bm25_index_id=existing_bm25,
            ),
            update,
            object(),
        )


@pytest.mark.asyncio
async def test_update_uses_the_explicit_change_and_the_persisted_other_binding(
    monkeypatch,
    explicit_binding_dependencies,
):
    persisted = []

    async def get_profile(profile_id, session):
        return _crag_profile(0.5)

    async def update_simulation(simulation, simulation_in, session):
        persisted.append(simulation_in)
        return simulation

    monkeypatch.setattr(
        simulations_service.rag_profiles_repo,
        "get_rag_profile_by_id",
        get_profile,
    )
    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        update_simulation,
    )
    monkeypatch.setattr(simulations_service, "_read_simulation", lambda value: value)

    result = await simulations_service.update_simulation_srvc(
        _simulation(corpus_index_id=101, bm25_index_id=202),
        SimulationUpdateRequest(bm25_index_id=203),
        object(),
    )

    assert result.bm25_index_id == 202
    assert persisted[0].model_dump(exclude_unset=True) == {"bm25_index_id": 203}
    assert explicit_binding_dependencies["dense"] == [(44, 101)]
    assert explicit_binding_dependencies["bm25"] == [(44, 203)]


@pytest.mark.asyncio
async def test_graphrag_keeps_its_dense_only_binding_contract(
    monkeypatch,
    explicit_binding_dependencies,
):
    graph = SimpleNamespace(id=91)

    async def validate_graph_profile(rag_profile, *, corpus_index_id, session):
        assert corpus_index_id == 101
        return graph

    monkeypatch.setattr(
        simulations_service,
        "_validate_graphrag_profile_for_index",
        validate_graph_profile,
    )

    result = await simulations_service._validate_retrieval_bindings_for_profile(
        corpus_id=44,
        corpus_index_id=101,
        bm25_index_id=None,
        rag_profile=SimpleNamespace(id=7, strategy="graphrag", config={}),
        session=object(),
    )

    assert result is graph
    assert explicit_binding_dependencies["dense"] == [(44, 101)]
    assert explicit_binding_dependencies["bm25"] == []


@pytest.mark.asyncio
async def test_create_preserves_graphrag_dense_only_binding_behavior(
    monkeypatch,
    explicit_binding_dependencies,
):
    graph = SimpleNamespace(id=91)
    persisted = []
    locked_graphs = []

    async def get_profile(profile_id, session):
        return SimpleNamespace(id=7, strategy="graphrag", config={})

    async def validate_graph_profile(rag_profile, *, corpus_index_id, session):
        assert corpus_index_id == 101
        return graph

    async def get_prompt_template(prompt_id, role, session):
        return None

    async def create_simulation(simulation_in, session):
        persisted.append(simulation_in)
        return simulation_in

    async def lock_knowledge_graph(knowledge_graph, session):
        locked_graphs.append(knowledge_graph)

    monkeypatch.setattr(
        simulations_service.rag_profiles_repo,
        "get_rag_profile_by_id",
        get_profile,
    )
    monkeypatch.setattr(
        simulations_service,
        "_validate_graphrag_profile_for_index",
        validate_graph_profile,
    )
    monkeypatch.setattr(simulations_service, "_get_prompt_template", get_prompt_template)
    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "create_simulation",
        create_simulation,
    )
    monkeypatch.setattr(
        simulations_service.knowledge_graph_indices_repo,
        "lock_knowledge_graph",
        lock_knowledge_graph,
    )
    monkeypatch.setattr(simulations_service, "_read_simulation", lambda value: value)

    result = await simulations_service.create_simulation_srvc(
        SimulationCreateRequest(
            name="GraphRAG create binding",
            corpus_id=44,
            corpus_index_id=101,
            bm25_index_id=None,
            rag_profile_id=7,
        ),
        object(),
        SimpleNamespace(id=1),
    )

    assert result is persisted[0]
    assert persisted[0].corpus_index_id == 101
    assert persisted[0].bm25_index_id is None
    assert locked_graphs == [graph]
    assert explicit_binding_dependencies["dense"] == [(44, 101)]
    assert explicit_binding_dependencies["bm25"] == []
