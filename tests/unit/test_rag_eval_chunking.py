from langchain_core.documents import Document


def test_prepare_evaluation_chunks_dispatches_semantic_and_aligns_offsets(monkeypatch):
    from app.airag.evaluation import eval_chunking

    captured = {}

    def semantic(documents, **kwargs):
        captured["kwargs"] = kwargs
        return [
            Document(page_content="Alpha beta", metadata=dict(documents[0].metadata)),
            Document(page_content="gamma delta", metadata=dict(documents[0].metadata)),
        ]

    monkeypatch.setattr(eval_chunking, "chunk_document_list_semantic", semantic)
    chunks = eval_chunking.prepare_evaluation_chunks(
        [Document(page_content="Alpha beta gamma delta", metadata={"eval_document_id": "doc"})],
        {"strategy": "semantic", "config": {"buffer_size": 2}},
    )

    assert captured["kwargs"] == {
        "breakpoint_threshold_type": "percentile",
        "breakpoint_threshold_amount": 90,
        "buffer_size": 2,
    }
    assert [chunk.metadata["start_index"] for chunk in chunks] == [0, 11]
    assert [chunk.metadata["end_index"] for chunk in chunks] == [10, 22]
    assert [chunk.metadata["chunk_index"] for chunk in chunks] == [0, 1]


def test_prepare_evaluation_chunks_rejects_unalignable_chunk(monkeypatch):
    from app.airag.evaluation import eval_chunking
    import pytest

    monkeypatch.setattr(
        eval_chunking,
        "chunk_document_list_recursive",
        lambda *_args, **_kwargs: [Document(page_content="not present", metadata={"eval_document_id": "doc"})],
    )

    with pytest.raises(ValueError, match="cannot be aligned"):
        eval_chunking.prepare_evaluation_chunks(
            [Document(page_content="present", metadata={"eval_document_id": "doc"})],
            {"strategy": "recursive", "config": {}},
        )
