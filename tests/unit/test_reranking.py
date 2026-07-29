from langchain_core.documents import Document

from app.airag.reranking import reranking


def test_choose_reranker_uses_cross_encoder_by_default(monkeypatch):
    captured = {}

    def fake_cross_encoder(question, docs, top_k):
        captured["question"] = question
        captured["docs"] = docs
        captured["top_k"] = top_k
        return [
            Document(
                page_content=docs[1].page_content,
                metadata={"source": "b", "rerank_score": 0.9},
            )
        ]

    monkeypatch.setattr(reranking, "cross_encoder_rerank", fake_cross_encoder)

    selected = reranking.choose_reranker()
    docs = [
        Document(page_content="alpha", metadata={"source": "a"}),
        Document(page_content="beta", metadata={"source": "b"}),
    ]

    result = selected("question", docs, 1)

    assert captured == {"question": "question", "docs": docs, "top_k": 1}
    assert [doc.page_content for doc in result] == ["beta"]
    assert result[0].metadata["rerank_score"] == 0.9


def test_choose_reranker_none_preserves_order_and_caps_documents():
    selected = reranking.choose_reranker("none")
    docs = [
        Document(page_content="alpha", metadata={"source": "a"}),
        Document(page_content="beta", metadata={"source": "b"}),
    ]

    result = selected("question", docs, 1)

    assert [doc.page_content for doc in result] == ["alpha"]
    assert "rerank_score" not in result[0].metadata
    assert result[0] is not docs[0]


def test_reranker_clone_preserves_hybrid_rank_and_score_metadata(monkeypatch):
    class FakeCrossEncoder:
        def predict(self, pairs):
            assert pairs == [("question", "alpha")]
            return [0.91]

    monkeypatch.setattr(reranking, "get_cross_encoder", lambda: FakeCrossEncoder())
    docs = [
        Document(
            page_content="alpha",
            metadata={
                "document_chunk_id": 7,
                "dense_rank": 2,
                "bm25_rank": 1,
                "fused_score": 0.75,
            },
        )
    ]

    result = reranking.cross_encoder_rerank("question", docs, 1)

    assert result[0] is not docs[0]
    assert result[0].metadata["dense_rank"] == 2
    assert result[0].metadata["bm25_rank"] == 1
    assert result[0].metadata["fused_score"] == 0.75
    assert result[0].metadata["rerank_score"] == 0.91


def test_choose_reranker_rejects_unknown_backend():
    try:
        reranking.choose_reranker("mystery")
    except ValueError as exc:
        assert "Unknown reranker" in str(exc)
    else:
        raise AssertionError("choose_reranker should reject unknown backends")
