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


def test_choose_reranker_none_preserves_documents_without_truncation():
    selected = reranking.choose_reranker("none")
    docs = [
        Document(page_content="alpha", metadata={"source": "a"}),
        Document(page_content="beta", metadata={"source": "b"}),
    ]

    result = selected("question", docs, 1)

    assert [doc.page_content for doc in result] == ["alpha", "beta"]
    assert "rerank_score" not in result[0].metadata
    assert result[0] is not docs[0]


def test_choose_reranker_rejects_unknown_backend():
    try:
        reranking.choose_reranker("mystery")
    except ValueError as exc:
        assert "Unknown reranker" in str(exc)
    else:
        raise AssertionError("choose_reranker should reject unknown backends")
