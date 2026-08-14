from types import SimpleNamespace

import pytest

from app.schemas.simulations_schemas import (
    SimulationRetrievalCompatiblePair,
    SimulationRetrievalIndexOption,
    SimulationRetrievalOptionsResponse,
)
from app.services import simulation_retrieval_options_service
from app.services.simulation_retrieval_options_service import (
    ensure_hybrid_indices_compatible,
    get_simulation_retrieval_options_srvc,
)


def _dense(**overrides):
    values = {
        "id": 101,
        "name": "Synthetic dense A",
        "corpus_id": 44,
        "chunking_profile_id": 9,
        "status": "built",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _bm25(chunk_ids=(10, 11), **overrides):
    values = {
        "id": 202,
        "name": "Synthetic BM25 A",
        "corpus_id": 44,
        "chunking_profile_id": 9,
        "status": "built",
        "document_count": len(chunk_ids),
        "document_chunk_ids_checksum": (
            "cc8a76beb67f521ca37f263f8297711998a9beb24599572d757352664be9aa6d"
        ),
        "compressed_artifact_checksum": "a" * 64,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_exact_synthetic_pair_is_compatible():
    ensure_hybrid_indices_compatible(
        corpus_id=44,
        corpus_index=_dense(),
        bm25_index=_bm25(),
        dense_chunk_ids=[10, 11],
    )


@pytest.mark.parametrize(
    ("dense", "bm25", "chunk_ids", "message"),
    [
        (_dense(status="failed"), _bm25(), [10, 11], "built"),
        (_dense(), _bm25(status="failed"), [10, 11], "built"),
        (_dense(corpus_id=45), _bm25(), [10, 11], "same corpus"),
        (_dense(), _bm25(chunking_profile_id=8), [10, 11], "chunking profile"),
        (_dense(), _bm25(), [10], "same document count"),
        (_dense(), _bm25(), [12, 13], "same chunk set"),
        (
            _dense(),
            _bm25(compressed_artifact_checksum=None),
            [10, 11],
            "artifact checksum",
        ),
    ],
)
def test_inexact_synthetic_pairs_are_rejected(dense, bm25, chunk_ids, message):
    with pytest.raises(ValueError, match=message):
        ensure_hybrid_indices_compatible(
            corpus_id=44,
            corpus_index=dense,
            bm25_index=bm25,
            dense_chunk_ids=chunk_ids,
        )


def test_retrieval_options_schema_contains_only_safe_option_metadata():
    response = SimulationRetrievalOptionsResponse(
        mode="hybrid",
        dense_indices=[SimulationRetrievalIndexOption(id=101, name="Dense")],
        bm25_indices=[SimulationRetrievalIndexOption(id=202, name="BM25")],
        compatible_pairs=[
            SimulationRetrievalCompatiblePair(
                corpus_index_id=101,
                bm25_index_id=202,
            )
        ],
    )

    payload = response.model_dump()

    assert payload["mode"] == "hybrid"
    assert set(payload["dense_indices"][0]) == {"id", "name"}
    assert set(payload["bm25_indices"][0]) == {"id", "name"}


def _install_resource_fakes(
    monkeypatch,
    *,
    profile,
    dense_candidates=None,
    bm25_candidates=None,
    dense_chunk_ids=None,
):
    async def get_corpus(corpus_id, session):
        return SimpleNamespace(id=corpus_id)

    async def get_profile(profile_id, session):
        return profile

    async def list_dense(corpus_id, session):
        return list(dense_candidates or [])

    async def list_bm25(corpus_id, session):
        return list(bm25_candidates or [])

    async def get_chunk_ids(corpus_index_id, session):
        return list((dense_chunk_ids or {}).get(corpus_index_id, []))

    monkeypatch.setattr(
        simulation_retrieval_options_service.corpus_repo,
        "get_corpus_by_id",
        get_corpus,
    )
    monkeypatch.setattr(
        simulation_retrieval_options_service.rag_profiles_repo,
        "get_rag_profile_by_id",
        get_profile,
    )
    monkeypatch.setattr(
        simulation_retrieval_options_service.corpus_indices_repo,
        "list_built_corpus_indices_for_corpus",
        list_dense,
    )
    monkeypatch.setattr(
        simulation_retrieval_options_service.corpus_bm25_indices_repo,
        "list_built_corpus_bm25_index_metadata_for_corpus",
        list_bm25,
    )
    monkeypatch.setattr(
        simulation_retrieval_options_service.indexed_chunks_repo,
        "get_document_chunk_ids_by_corpus_index_id",
        get_chunk_ids,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("weight", "mode", "dense_ids", "bm25_ids"),
    [
        (0.0, "dense", [101], []),
        (1.0, "bm25", [], [202]),
    ],
)
async def test_profile_mode_returns_only_the_required_artifact_kind(
    monkeypatch,
    weight,
    mode,
    dense_ids,
    bm25_ids,
):
    _install_resource_fakes(
        monkeypatch,
        profile=SimpleNamespace(id=7, strategy="crag", config={"bm25_weight": weight}),
        dense_candidates=[_dense()],
        bm25_candidates=[_bm25()],
    )

    result = await get_simulation_retrieval_options_srvc(
        corpus_id=44,
        rag_profile_id=7,
        session=object(),
    )

    assert result.mode == mode
    assert [item.id for item in result.dense_indices] == dense_ids
    assert [item.id for item in result.bm25_indices] == bm25_ids
    assert result.compatible_pairs == []


@pytest.mark.asyncio
async def test_hybrid_options_exclude_same_count_different_checksum_dense_index(
    monkeypatch,
):
    _install_resource_fakes(
        monkeypatch,
        profile=SimpleNamespace(
            id=7,
            strategy="crag",
            config={"bm25_weight": 0.25},
        ),
        dense_candidates=[_dense(), _dense(id=102, name="Synthetic dense B")],
        bm25_candidates=[_bm25()],
        dense_chunk_ids={101: [10, 11], 102: [12, 13]},
    )

    result = await get_simulation_retrieval_options_srvc(
        corpus_id=44,
        rag_profile_id=7,
        session=object(),
    )

    assert result.mode == "hybrid"
    assert [(item.id, item.name) for item in result.dense_indices] == [
        (101, "Synthetic dense A")
    ]
    assert [(item.id, item.name) for item in result.bm25_indices] == [
        (202, "Synthetic BM25 A")
    ]
    assert [pair.model_dump() for pair in result.compatible_pairs] == [
        {"corpus_index_id": 101, "bm25_index_id": 202}
    ]


@pytest.mark.asyncio
async def test_hybrid_options_return_empty_lists_when_no_exact_pair_exists(monkeypatch):
    _install_resource_fakes(
        monkeypatch,
        profile=SimpleNamespace(id=7, strategy="crag", config={"bm25_weight": 0.5}),
        dense_candidates=[_dense()],
        bm25_candidates=[_bm25()],
        dense_chunk_ids={101: [12, 13]},
    )

    result = await get_simulation_retrieval_options_srvc(
        corpus_id=44,
        rag_profile_id=7,
        session=object(),
    )

    assert result.dense_indices == []
    assert result.bm25_indices == []
    assert result.compatible_pairs == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("missing", "message"),
    [("corpus", "Corpus not found"), ("profile", "RAG profile not found")],
)
async def test_retrieval_options_reject_missing_resources(
    monkeypatch,
    missing,
    message,
):
    async def get_corpus(corpus_id, session):
        return None if missing == "corpus" else SimpleNamespace(id=corpus_id)

    async def get_profile(profile_id, session):
        return None if missing == "profile" else SimpleNamespace(
            id=profile_id,
            strategy="crag",
            config={"bm25_weight": 0.0},
        )

    monkeypatch.setattr(
        simulation_retrieval_options_service.corpus_repo,
        "get_corpus_by_id",
        get_corpus,
    )
    monkeypatch.setattr(
        simulation_retrieval_options_service.rag_profiles_repo,
        "get_rag_profile_by_id",
        get_profile,
    )

    with pytest.raises(ValueError, match=message):
        await get_simulation_retrieval_options_srvc(
            corpus_id=44,
            rag_profile_id=7,
            session=object(),
        )


@pytest.mark.asyncio
async def test_retrieval_options_reject_non_crag_profile(monkeypatch):
    _install_resource_fakes(
        monkeypatch,
        profile=SimpleNamespace(id=7, strategy="graphrag", config={}),
    )

    with pytest.raises(ValueError, match="require a CRAG profile"):
        await get_simulation_retrieval_options_srvc(
            corpus_id=44,
            rag_profile_id=7,
            session=object(),
        )
