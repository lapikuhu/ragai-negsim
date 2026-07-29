from types import SimpleNamespace
import asyncio

import pytest

from app.repositories.corpus_bm25_indices_repo import document_chunk_ids_checksum
from app.schemas.simulations_schemas import (
    SimulationCreateRequest,
    SimulationUpdateRequest,
)
from app.services import simulations_service


@pytest.fixture(autouse=True)
def isolate_negotiation_graph_cache():
    simulations_service.NEGOTIATION_GRAPH_CACHE.clear()
    yield
    simulations_service.NEGOTIATION_GRAPH_CACHE.clear()


def _simulation(*, corpus_index_id=77, bm25_index_id=88):
    return SimpleNamespace(
        corpus_id=200,
        corpus_index_id=corpus_index_id,
        bm25_index_id=bm25_index_id,
        rag_profile_id=500,
    )


class RuntimeHarness:
    def __init__(self, monkeypatch, *, weight=0.5, strategy="crag"):
        self.events = []
        self.profile = SimpleNamespace(
            id=500,
            strategy=strategy,
            knowledge_graph_index_id=8 if strategy == "graphrag" else None,
            config={
                "bm25_weight": weight,
                "dense_k": 6,
                "bm25_k": 7,
                "final_top_k": 4,
                "reranker": "none",
                "top_n": 4,
            },
        )
        self.dense_index = SimpleNamespace(
            id=77,
            corpus_id=200,
            chunking_profile_id=5,
            vector_store_id=12,
            status="built",
            embedding_model="dense-model",
            embedding_dimensions=384,
            vector_namespace="dense-77",
        )
        self.chunk_ids = [20, 3]
        self.bm25_metadata = SimpleNamespace(
            id=88,
            corpus_id=200,
            chunking_profile_id=5,
            status="built",
            format_version="pickle-zlib-v1",
            document_count=2,
            document_chunk_ids_checksum=document_chunk_ids_checksum(self.chunk_ids),
            compressed_artifact_checksum="a" * 64,
        )
        self.vector_store = SimpleNamespace(id=12, backend="fake")
        self.artifact = b"artifact"
        self.dense_runtime = object()
        self.dense_retriever = object()
        self.bm25_retriever = object()

        async def get_profile(profile_id, session):
            self.events.append("profile")
            return self.profile

        async def get_dense(index_id, session):
            self.events.append("dense_metadata")
            return self.dense_index

        async def get_bm25(index_id, session):
            self.events.append("bm25_metadata")
            return self.bm25_metadata

        async def get_chunk_ids(index_id, session):
            self.events.append("dense_chunk_ids")
            return list(self.chunk_ids)

        async def get_vector_store(vector_store_id, session):
            self.events.append("vector_store")
            return self.vector_store

        async def get_artifact(index_id, session):
            self.events.append("bm25_artifact")
            return self.artifact

        async def instantiate_dense(index, vector_store):
            self.events.append("dense_runtime")
            return self.dense_runtime

        def make_dense(runtime, k=4, metadata_filter=None):
            self.events.append(("dense_factory", k, metadata_filter))
            return self.dense_retriever

        async def load_bm25(artifact, **kwargs):
            self.events.append(("bm25_load", artifact, kwargs))
            return self.bm25_retriever

        def make_hybrid(**kwargs):
            self.events.append(("hybrid_factory", kwargs))
            return ("hybrid", kwargs)

        def normalize(strategy_name, config):
            return ("normalized", strategy_name, config)

        def build_pipeline(retriever, config):
            return ("pipeline", retriever, config)

        async def get_graph(graph_id, session):
            self.events.append("knowledge_graph")
            return SimpleNamespace(
                id=graph_id,
                status="built",
                active_generation="generation-1",
                corpus_index_id=77,
            )

        monkeypatch.setattr(
            simulations_service.rag_profiles_repo,
            "get_rag_profile_by_id",
            get_profile,
        )
        monkeypatch.setattr(
            simulations_service.corpus_indices_repo,
            "get_corpus_index_by_id",
            get_dense,
        )
        monkeypatch.setattr(
            simulations_service.vector_stores_repo,
            "get_vector_store_by_id",
            get_vector_store,
        )
        monkeypatch.setattr(
            simulations_service,
            "_instantiate_vector_store_for_index",
            instantiate_dense,
        )
        monkeypatch.setattr(simulations_service, "make_dense_retriever", make_dense)
        monkeypatch.setattr(
            simulations_service,
            "aload_validated_bm25_artifact",
            load_bm25,
            raising=False,
        )
        monkeypatch.setattr(
            simulations_service,
            "make_hybrid_retriever",
            make_hybrid,
            raising=False,
        )
        monkeypatch.setattr(
            simulations_service,
            "normalize_response_pipeline_config",
            normalize,
        )
        monkeypatch.setattr(
            simulations_service,
            "build_response_pipeline",
            build_pipeline,
        )
        monkeypatch.setattr(
            simulations_service.knowledge_graph_indices_repo,
            "get_knowledge_graph_index_by_id",
            get_graph,
        )
        monkeypatch.setattr(
            simulations_service,
            "corpus_bm25_indices_repo",
            SimpleNamespace(
                get_corpus_bm25_index_metadata_by_id=get_bm25,
                get_corpus_bm25_index_artifact_by_id=get_artifact,
                document_chunk_ids_checksum=document_chunk_ids_checksum,
            ),
            raising=False,
        )
        monkeypatch.setattr(
            simulations_service,
            "indexed_chunks_repo",
            SimpleNamespace(
                get_document_chunk_ids_by_corpus_index_id=get_chunk_ids,
            ),
            raising=False,
        )


def test_runtime_crag_settings_reject_removed_legacy_top_k():
    with pytest.raises(ValueError, match="top_k"):
        simulations_service._crag_retrieval_settings(
            SimpleNamespace(config={"top_k": 9})
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("backend", "expected_call"),
    [
        (
            "chroma",
            {
                "embedding_model": "embedding",
                "collection_name": "dense-collection",
                "persist_directory": "./dense-store",
            },
        ),
        (
            "faiss",
            {
                "embeddings": "embedding",
                "path": "./dense-store",
            },
        ),
        (
            "pgvector",
            {
                "vector_table_name": "dense_table",
                "embedding_model": "embedding",
                "embedding_model_name": "dense-model",
            },
        ),
    ],
)
async def test_dense_factory_dispatch_preserves_chroma_faiss_and_pgvector_paths(
    monkeypatch,
    backend,
    expected_call,
):
    calls = []
    selector_calls = []
    expected_runtime = object()
    corpus_index = SimpleNamespace(embedding_model="dense-model")
    vector_store = SimpleNamespace(
        backend=backend,
        collection_name="dense-collection",
        path="./dense-store",
        table_name="dense_table",
    )

    def choose_embedding_model(model_name):
        selector_calls.append(model_name)
        return "embedding", {"model": model_name}

    monkeypatch.setattr(simulations_service, "choose_embedding_model", choose_embedding_model)

    if backend == "pgvector":
        async def factory(**kwargs):
            calls.append(kwargs)
            return expected_runtime

        monkeypatch.setattr(simulations_service, "instantiate_pgvector_store", factory)
    elif backend == "chroma":
        def factory(**kwargs):
            calls.append(kwargs)
            return expected_runtime

        monkeypatch.setattr(simulations_service, "instantiate_chroma_vector_store", factory)
    else:
        def factory(**kwargs):
            calls.append(kwargs)
            return expected_runtime

        monkeypatch.setattr(simulations_service, "load_faiss_vector_store", factory)

    result = await simulations_service._instantiate_vector_store_for_index(
        corpus_index,
        vector_store,
    )

    assert result is expected_runtime
    assert calls == [expected_call]
    assert selector_calls == ["dense-model"]


@pytest.mark.asyncio
async def test_dense_only_uses_dense_k_without_fetching_bm25(monkeypatch):
    harness = RuntimeHarness(monkeypatch, weight=0.0)

    strategy, pipeline = await simulations_service._get_retrieval_graph_for_simulation(
        _simulation(),
        object(),
    )

    assert strategy == "crag"
    assert pipeline[0] == "pipeline"
    assert ("dense_factory", 6, {"corpus_index_id": 77}) in harness.events
    assert not any(
        event == "bm25_metadata"
        or event == "bm25_artifact"
        or (isinstance(event, tuple) and event[0] == "bm25_load")
        for event in harness.events
    )


@pytest.mark.asyncio
async def test_bm25_only_never_accesses_dense_index_or_vector_store(monkeypatch):
    harness = RuntimeHarness(monkeypatch, weight=1.0)

    strategy, pipeline = await simulations_service._get_retrieval_graph_for_simulation(
        _simulation(corpus_index_id=77),
        object(),
    )

    assert strategy == "crag"
    assert pipeline[0] == "pipeline"
    assert "dense_metadata" not in harness.events
    assert "dense_chunk_ids" not in harness.events
    assert "vector_store" not in harness.events
    assert not any(
        isinstance(event, tuple) and event[0] == "dense_factory"
        for event in harness.events
    )
    load_event = next(
        event
        for event in harness.events
        if isinstance(event, tuple) and event[0] == "bm25_load"
    )
    assert load_event[2]["k"] == 7


@pytest.mark.asyncio
async def test_create_bm25_only_persists_explicit_binding_without_dense_access(
    monkeypatch,
):
    harness = RuntimeHarness(monkeypatch, weight=1.0)
    captured = []

    async def create_simulation(simulation_in, session):
        captured.append(simulation_in)
        return simulation_in

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "create_simulation",
        create_simulation,
    )
    monkeypatch.setattr(simulations_service, "_read_simulation", lambda value: value)

    result = await simulations_service.create_simulation_srvc(
        SimulationCreateRequest(
            name="BM25-only simulation",
            corpus_id=200,
            corpus_index_id=None,
            bm25_index_id=88,
            rag_profile_id=500,
        ),
        object(),
        SimpleNamespace(id=7),
    )

    assert result is captured[0]
    assert captured[0].corpus_index_id is None
    assert captured[0].bm25_index_id == 88
    assert "dense_metadata" not in harness.events
    assert "vector_store" not in harness.events
    assert "bm25_artifact" not in harness.events


@pytest.mark.asyncio
async def test_update_can_clear_dense_binding_for_bm25_only_profile(monkeypatch):
    harness = RuntimeHarness(monkeypatch, weight=1.0)
    captured = []
    simulation = _simulation(corpus_index_id=77, bm25_index_id=88)

    async def update_simulation(simulation_obj, simulation_in, session):
        captured.append(simulation_in)
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        update_simulation,
    )
    monkeypatch.setattr(simulations_service, "_read_simulation", lambda value: value)

    await simulations_service.update_simulation_srvc(
        simulation,
        SimulationUpdateRequest(corpus_index_id=None, bm25_index_id=88),
        object(),
    )

    assert captured[0].model_dump(exclude_unset=True) == {
        "corpus_index_id": None,
        "bm25_index_id": 88,
    }
    assert "dense_metadata" not in harness.events
    assert "vector_store" not in harness.events


@pytest.mark.asyncio
async def test_bm25_mode_requires_explicit_binding_and_never_infers_dense_id(
    monkeypatch,
):
    harness = RuntimeHarness(monkeypatch, weight=1.0)

    with pytest.raises(ValueError, match="BM25 index selection"):
        await simulations_service._get_retrieval_graph_for_simulation(
            _simulation(corpus_index_id=88, bm25_index_id=None),
            object(),
        )

    assert "bm25_metadata" not in harness.events


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_dense", "dense corpus index selection"),
        ("missing_bm25", "BM25 index selection"),
        ("dense_unbuilt", "Corpus index must be built"),
        ("bm25_unbuilt", "BM25 index must be built"),
        ("corpus", "same corpus"),
        ("profile", "same chunking profile"),
        ("count", "same document count"),
        ("checksum", "same chunk set"),
    ],
)
async def test_hybrid_rejects_missing_unbuilt_or_incompatible_bindings_before_build(
    monkeypatch,
    mutation,
    message,
):
    harness = RuntimeHarness(monkeypatch, weight=0.4)
    simulation = _simulation()
    if mutation == "missing_dense":
        simulation.corpus_index_id = None
    elif mutation == "missing_bm25":
        simulation.bm25_index_id = None
    elif mutation == "dense_unbuilt":
        harness.dense_index.status = "created"
    elif mutation == "bm25_unbuilt":
        harness.bm25_metadata.status = "created"
    elif mutation == "corpus":
        harness.bm25_metadata.corpus_id = 999
    elif mutation == "profile":
        harness.bm25_metadata.chunking_profile_id = 99
    elif mutation == "count":
        harness.bm25_metadata.document_count = 3
    elif mutation == "checksum":
        harness.bm25_metadata.document_chunk_ids_checksum = "b" * 64

    with pytest.raises(ValueError, match=message):
        await simulations_service._get_retrieval_graph_for_simulation(
            simulation,
            object(),
        )

    assert "vector_store" not in harness.events
    assert "bm25_artifact" not in harness.events
    assert not any(
        isinstance(event, tuple)
        and event[0] in {"dense_factory", "bm25_load", "hybrid_factory"}
        for event in harness.events
    )


@pytest.mark.asyncio
async def test_compatible_hybrid_validates_before_constructing_both_retrievers(
    monkeypatch,
):
    harness = RuntimeHarness(monkeypatch, weight=0.4)

    strategy, pipeline = await simulations_service._get_retrieval_graph_for_simulation(
        _simulation(),
        object(),
    )

    assert strategy == "crag"
    assert pipeline[0] == "pipeline"
    validation_end = harness.events.index("dense_chunk_ids")
    construction_events = [
        index
        for index, event in enumerate(harness.events)
        if isinstance(event, tuple)
        and event[0] in {"dense_factory", "bm25_load", "hybrid_factory"}
    ]
    assert construction_events
    assert all(index > validation_end for index in construction_events)
    hybrid_event = next(
        event
        for event in harness.events
        if isinstance(event, tuple) and event[0] == "hybrid_factory"
    )
    assert hybrid_event[1] == {
        "dense_retriever": harness.dense_retriever,
        "bm25_retriever": harness.bm25_retriever,
        "bm25_weight": 0.4,
        "dense_k": 6,
        "bm25_k": 7,
        "final_top_k": 4,
    }


def test_graph_cache_key_tracks_dense_bm25_artifact_and_chunk_snapshot():
    common = (
        SimpleNamespace(id=77),
        SimpleNamespace(id=12),
        {"coach": None, "counterpart": None, "evaluator": None},
        SimpleNamespace(id=500, strategy="crag", config={"bm25_weight": 1.0}),
    )
    first = simulations_service._graph_cache_key(
        *common,
        bm25_index=SimpleNamespace(
            id=88,
            compressed_artifact_checksum="a" * 64,
            document_chunk_ids_checksum="b" * 64,
        ),
    )
    second = simulations_service._graph_cache_key(
        *common,
        bm25_index=SimpleNamespace(
            id=88,
            compressed_artifact_checksum="c" * 64,
            document_chunk_ids_checksum="b" * 64,
        ),
    )
    different_dense = simulations_service._graph_cache_key(
        SimpleNamespace(id=78),
        *common[1:],
        bm25_index=SimpleNamespace(
            id=88,
            compressed_artifact_checksum="a" * 64,
            document_chunk_ids_checksum="b" * 64,
        ),
    )
    different_chunk_snapshot = simulations_service._graph_cache_key(
        *common,
        bm25_index=SimpleNamespace(
            id=88,
            compressed_artifact_checksum="a" * 64,
            document_chunk_ids_checksum="d" * 64,
        ),
    )

    assert first != second
    assert first != different_dense
    assert first != different_chunk_snapshot


def test_resource_specific_cache_clearing_uses_only_matching_identity():
    simulations_service.NEGOTIATION_GRAPH_CACHE.clear()
    common = (
        SimpleNamespace(id=77),
        SimpleNamespace(id=12),
        {"coach": None, "counterpart": None, "evaluator": None},
        SimpleNamespace(id=500, strategy="crag", config={"bm25_weight": 0.5}),
    )
    target = simulations_service._graph_cache_key(
        *common,
        bm25_index=SimpleNamespace(
            id=88,
            compressed_artifact_checksum="a" * 64,
            document_chunk_ids_checksum="b" * 64,
        ),
    )
    other_dense = simulations_service._graph_cache_key(
        SimpleNamespace(id=78),
        *common[1:],
        bm25_index=SimpleNamespace(
            id=89,
            compressed_artifact_checksum="c" * 64,
            document_chunk_ids_checksum="d" * 64,
        ),
    )
    simulations_service.NEGOTIATION_GRAPH_CACHE.update(
        {target: "target", other_dense: "other"}
    )

    assert (
        simulations_service.clear_negotiation_graph_cache_for_corpus_index(77)
        == 1
    )
    assert target not in simulations_service.NEGOTIATION_GRAPH_CACHE
    assert simulations_service.NEGOTIATION_GRAPH_CACHE[other_dense] == "other"

    simulations_service.NEGOTIATION_GRAPH_CACHE[target] = "target"
    assert (
        simulations_service.clear_negotiation_graph_cache_for_bm25_index(
            88,
            artifact_checksum="a" * 64,
            document_chunk_ids_checksum="b" * 64,
        )
        == 1
    )
    assert target not in simulations_service.NEGOTIATION_GRAPH_CACHE
    assert simulations_service.NEGOTIATION_GRAPH_CACHE[other_dense] == "other"


def test_cache_eviction_prevents_in_flight_graph_from_repopulating_cache():
    simulations_service.NEGOTIATION_GRAPH_CACHE.clear()
    cache_key = ("in-flight",)
    construction_epoch = simulations_service.NEGOTIATION_GRAPH_CACHE_EPOCH

    simulations_service.clear_negotiation_graph_cache_for_corpus_index(77)
    cached = simulations_service._cache_negotiation_graph_if_current(
        cache_key,
        "stale graph",
        construction_epoch,
    )

    assert cached is False
    assert cache_key not in simulations_service.NEGOTIATION_GRAPH_CACHE


@pytest.mark.asyncio
async def test_graph_started_before_eviction_is_returned_but_not_cached(monkeypatch):
    simulations_service.NEGOTIATION_GRAPH_CACHE.clear()
    runtime_started = asyncio.Event()
    allow_runtime = asyncio.Event()
    runtime = SimpleNamespace(
        corpus_index=SimpleNamespace(id=77),
        vector_store=SimpleNamespace(id=12),
        rag_profile=SimpleNamespace(id=500, strategy="crag", config={}),
        knowledge_graph=None,
        bm25_index=None,
        bm25_artifact=None,
    )

    async def get_runtime(simulation, session):
        runtime_started.set()
        await allow_runtime.wait()
        return runtime

    async def get_prompts(simulation, session):
        return {}, {"coach": None, "counterpart": None, "evaluator": None}

    async def build_retrieval(**kwargs):
        return "crag", "rag graph"

    monkeypatch.setattr(
        simulations_service,
        "_get_retrieval_runtime_for_simulation",
        get_runtime,
    )
    monkeypatch.setattr(
        simulations_service,
        "_llm_selection_from_simulation",
        lambda simulation: {"counterpart": {}, "evaluator": {}},
    )
    monkeypatch.setattr(
        simulations_service,
        "_get_simulation_prompt_templates",
        get_prompts,
    )
    monkeypatch.setattr(
        simulations_service,
        "_build_retrieval_graph",
        build_retrieval,
    )
    monkeypatch.setattr(
        simulations_service,
        "_build_selected_llm",
        lambda selection, operation: operation,
    )
    monkeypatch.setattr(
        simulations_service,
        "make_negotiation_graph",
        lambda **kwargs: ("negotiation graph", kwargs),
    )

    task = asyncio.create_task(
        simulations_service._get_negotiation_graph_for_simulation(
            object(),
            object(),
        )
    )
    await runtime_started.wait()
    simulations_service.clear_negotiation_graph_cache_for_corpus_index(77)
    allow_runtime.set()

    graph = await task

    assert graph[0] == "negotiation graph"
    assert simulations_service.NEGOTIATION_GRAPH_CACHE == {}


@pytest.mark.asyncio
async def test_graphrag_still_requires_explicit_dense_corpus_index(monkeypatch):
    RuntimeHarness(monkeypatch, strategy="graphrag")

    with pytest.raises(ValueError, match="GraphRAG requires a dense corpus index"):
        await simulations_service._get_retrieval_graph_for_simulation(
            _simulation(corpus_index_id=None, bm25_index_id=88),
            object(),
        )
