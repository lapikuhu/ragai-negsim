import asyncio
import inspect
import pickle
import threading
import zlib
from hashlib import sha256
from pathlib import Path

import pytest
from langchain_core.documents import Document

from app.airag.retrieval import retrievers


def _document(chunk_id, text=None, **metadata):
    return Document(
        page_content=text or f"chunk-{chunk_id}",
        metadata={"document_chunk_id": chunk_id, **metadata},
    )


class FakeRetriever:
    def __init__(self, documents):
        self.documents = documents
        self.calls = []
        self.call_details = []

    def invoke(self, query, config=None, **kwargs):
        self.calls.append(query)
        self.call_details.append((query, config, kwargs))
        return list(self.documents)


def test_bm25_artifact_round_trip_validates_checksum_format_count_and_ids():
    documents = [_document(10, "alpha beta"), _document(20, "beta gamma")]
    artifact = retrievers.build_serialized_bm25_artifact(documents, k=7)

    loaded = retrievers.load_validated_bm25_artifact(
        artifact,
        expected_checksum=sha256(artifact).hexdigest(),
        format_version="pickle-zlib-v1",
        expected_document_count=2,
    )

    assert loaded.k == 7
    assert [document.metadata["document_chunk_id"] for document in loaded.docs] == [
        10,
        20,
    ]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"expected_checksum": "0" * 64}, "checksum"),
        ({"format_version": "pickle-v2"}, "format"),
        ({"expected_document_count": 3}, "document count"),
    ],
)
def test_bm25_artifact_rejects_invalid_persisted_metadata(overrides, message):
    artifact = retrievers.build_serialized_bm25_artifact([_document(1, "alpha")])
    kwargs = {
        "expected_checksum": sha256(artifact).hexdigest(),
        "format_version": "pickle-zlib-v1",
        "expected_document_count": 1,
        **overrides,
    }

    with pytest.raises(ValueError, match=message):
        retrievers.load_validated_bm25_artifact(artifact, **kwargs)


def test_bm25_artifact_rejects_wrong_object_type():
    payload = zlib.compress(pickle.dumps({"not": "a retriever"}, protocol=5))

    with pytest.raises(ValueError, match="type"):
        retrievers.load_validated_bm25_artifact(
            payload,
            expected_checksum=sha256(payload).hexdigest(),
            format_version="pickle-zlib-v1",
            expected_document_count=1,
        )


@pytest.mark.parametrize("chunk_id", [None, True])
def test_bm25_artifact_rejects_invalid_document_ids(chunk_id):
    runtime = retrievers.make_bm25_retriever([_document(1, "alpha")])
    runtime.docs[0].metadata["document_chunk_id"] = chunk_id
    payload = zlib.compress(pickle.dumps(runtime, protocol=5))

    with pytest.raises(ValueError, match="integer document_chunk_id"):
        retrievers.load_validated_bm25_artifact(
            payload,
            expected_checksum=sha256(payload).hexdigest(),
            format_version="pickle-zlib-v1",
            expected_document_count=1,
        )


def test_bm25_artifact_rejects_corrupt_compressed_payload():
    payload = b"not-zlib"

    with pytest.raises(ValueError, match="cannot be loaded"):
        retrievers.load_validated_bm25_artifact(
            payload,
            expected_checksum=sha256(payload).hexdigest(),
            format_version="pickle-zlib-v1",
            expected_document_count=1,
        )


def test_bm25_artifact_rejects_non_protocol_five_pickle():
    runtime = retrievers.make_bm25_retriever([_document(1, "alpha")])
    payload = zlib.compress(pickle.dumps(runtime, protocol=4))

    with pytest.raises(ValueError, match="cannot be loaded"):
        retrievers.load_validated_bm25_artifact(
            payload,
            expected_checksum=sha256(payload).hexdigest(),
            format_version="pickle-zlib-v1",
            expected_document_count=1,
        )


def test_bm25_build_and_load_reject_payloads_over_150_mib(monkeypatch):
    class OversizedArtifact(bytes):
        def __len__(self):
            return 150 * 1024 * 1024 + 1

    artifact = retrievers.build_serialized_bm25_artifact([_document(1, "alpha")])
    oversized = OversizedArtifact(artifact)

    with pytest.raises(ValueError, match="150 MiB"):
        retrievers.load_validated_bm25_artifact(
            oversized,
            expected_checksum=sha256(oversized).hexdigest(),
            format_version="pickle-zlib-v1",
            expected_document_count=1,
        )

    monkeypatch.setattr(retrievers.zlib, "compress", lambda _payload: oversized)
    with pytest.raises(ValueError, match="150 MiB"):
        retrievers.build_serialized_bm25_artifact([_document(1, "alpha")])


@pytest.mark.asyncio
async def test_async_bm25_build_and_load_run_in_executor(monkeypatch):
    event_loop_thread = threading.get_ident()
    construction_threads = []
    load_threads = []
    original_make = retrievers.make_bm25_retriever
    original_load = retrievers.load_validated_bm25_artifact

    def recording_make(*args, **kwargs):
        construction_threads.append(threading.get_ident())
        return original_make(*args, **kwargs)

    def recording_load(*args, **kwargs):
        load_threads.append(threading.get_ident())
        return original_load(*args, **kwargs)

    monkeypatch.setattr(retrievers, "make_bm25_retriever", recording_make)
    artifact = await retrievers.abuild_serialized_bm25_artifact(
        [_document(1, "alpha")]
    )
    monkeypatch.setattr(retrievers, "load_validated_bm25_artifact", recording_load)
    loaded = await retrievers.aload_validated_bm25_artifact(
        artifact,
        expected_checksum=sha256(artifact).hexdigest(),
        format_version="pickle-zlib-v1",
        expected_document_count=1,
    )

    assert loaded.docs[0].metadata["document_chunk_id"] == 1
    assert construction_threads and construction_threads[0] != event_loop_thread
    assert load_threads and load_threads[0] != event_loop_thread


@pytest.mark.parametrize(
    ("weight", "expected_dense_calls", "expected_bm25_calls"),
    [(0.0, ["pricing"], []), (1.0, [], ["pricing"])],
)
def test_pure_modes_never_invoke_inactive_retriever(
    weight,
    expected_dense_calls,
    expected_bm25_calls,
):
    dense = FakeRetriever([_document(2, source="dense")])
    bm25 = FakeRetriever([_document(3, source="bm25")])
    hybrid = retrievers.make_hybrid_retriever(
        dense_retriever=dense,
        bm25_retriever=bm25,
        bm25_weight=weight,
        dense_k=3,
        bm25_k=2,
        final_top_k=2,
    )

    documents = hybrid.invoke("pricing")

    assert dense.calls == expected_dense_calls
    assert bm25.calls == expected_bm25_calls
    assert len(documents) == 1
    assert documents[0].metadata["fused_score"] == 1.0
    assert set(documents[0].metadata) >= {
        "source",
        "dense_rank",
        "bm25_rank",
        "fused_score",
    }
    inactive_rank = "bm25_rank" if weight == 0.0 else "dense_rank"
    assert documents[0].metadata[inactive_rank] is None


def test_hybrid_fuses_unequal_bounded_candidates_and_merges_duplicate_ids():
    dense = FakeRetriever(
        [
            _document(8, source="dense-eight"),
            _document(3, source="dense-three"),
            _document(8, source="duplicate"),
            _document(99, source="beyond-dense-k"),
        ]
    )
    bm25 = FakeRetriever(
        [
            _document(3, source="bm25-three"),
            _document(5, source="bm25-five"),
            _document(8, source="bm25-eight"),
            _document(77, source="beyond-bm25-k"),
        ]
    )
    hybrid = retrievers.make_hybrid_retriever(
        dense_retriever=dense,
        bm25_retriever=bm25,
        bm25_weight=0.25,
        dense_k=3,
        bm25_k=2,
        final_top_k=2,
    )

    documents = hybrid.invoke("pricing")

    assert [document.metadata["document_chunk_id"] for document in documents] == [8, 3]
    assert documents[0].metadata == {
        "document_chunk_id": 8,
        "source": "dense-eight",
        "dense_rank": 1,
        "bm25_rank": None,
        "fused_score": 0.75,
    }
    assert documents[1].metadata["dense_rank"] == 2
    assert documents[1].metadata["bm25_rank"] == 1
    assert documents[1].metadata["fused_score"] == pytest.approx(0.625)


def test_hybrid_duplicate_removal_preserves_original_source_ranks():
    hybrid = retrievers.make_hybrid_retriever(
        dense_retriever=FakeRetriever([_document(8), _document(8), _document(3)]),
        bm25_retriever=None,
        bm25_weight=0.0,
        dense_k=3,
        bm25_k=1,
        final_top_k=2,
    )

    documents = hybrid.invoke("duplicates")

    assert [document.metadata["document_chunk_id"] for document in documents] == [8, 3]
    assert documents[1].metadata["dense_rank"] == 3
    assert documents[1].metadata["fused_score"] == pytest.approx(1 / 3)


def test_hybrid_forwards_runnable_config_and_kwargs_to_active_retrievers():
    dense = FakeRetriever([_document(8)])
    bm25 = FakeRetriever([_document(3)])
    hybrid = retrievers.make_hybrid_retriever(
        dense_retriever=dense,
        bm25_retriever=bm25,
        bm25_weight=0.5,
        dense_k=1,
        bm25_k=1,
        final_top_k=1,
    )
    config = {"callbacks": ["trace"]}

    hybrid.invoke("pricing", config=config, run_name="hybrid")

    assert dense.call_details == [
        ("pricing", config, {"run_name": "hybrid"}),
    ]
    assert bm25.call_details == [
        ("pricing", config, {"run_name": "hybrid"}),
    ]


def test_hybrid_orders_equal_scores_by_ascending_chunk_id():
    hybrid = retrievers.make_hybrid_retriever(
        dense_retriever=FakeRetriever([_document(9)]),
        bm25_retriever=FakeRetriever([_document(4)]),
        bm25_weight=0.5,
        dense_k=2,
        bm25_k=2,
        final_top_k=2,
    )

    documents = hybrid.invoke("tie")

    assert [document.metadata["document_chunk_id"] for document in documents] == [4, 9]


@pytest.mark.parametrize("chunk_id", [None, "4", True])
def test_hybrid_rejects_missing_or_non_integer_chunk_ids(chunk_id):
    hybrid = retrievers.make_hybrid_retriever(
        dense_retriever=FakeRetriever([_document(chunk_id)]),
        bm25_retriever=None,
        bm25_weight=0.0,
        dense_k=1,
        bm25_k=1,
        final_top_k=1,
    )

    with pytest.raises(ValueError, match="integer document_chunk_id"):
        hybrid.invoke("invalid")


def test_no_production_retrieval_module_imports_ensemble_and_todo_is_adjacent():
    retrieval_dir = Path(retrievers.__file__).parent
    sources = "\n".join(
        path.read_text(encoding="utf-8") for path in retrieval_dir.rglob("*.py")
    )
    construction_source = inspect.getsource(retrievers.make_bm25_retriever)

    assert "EnsembleRetriever" not in sources
    assert (
        "# TODO: Introduce versioned BM25 text normalization/tokenization for documents and queries.\n"
        "    retriever = BM25Retriever.from_documents"
    ) in construction_source
