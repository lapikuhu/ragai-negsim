import builtins

from langchain_core.documents import Document

from app.airag.chains.crag import crag, crag_nodes


def test_make_crag_rerank_node_uses_rewritten_query_and_updates_documents():
    captured = {}

    def fake_reranker(question, docs, top_k):
        captured["question"] = question
        captured["docs"] = docs
        captured["top_k"] = top_k
        return [
            Document(
                page_content=docs[1].page_content,
                metadata={"source": "second", "rerank_score": 0.95},
            )
        ]

    node = crag_nodes.make_crag_rerank_node(fake_reranker, top_k=1)
    docs = [
        Document(page_content="alpha", metadata={"source": "first"}),
        Document(page_content="beta", metadata={"source": "second"}),
    ]

    result = node(
        {
            "question": "original question",
            "rewritten": "rewritten question",
            "documents": docs,
        }
    )

    assert captured == {
        "question": "rewritten question",
        "docs": docs,
        "top_k": 1,
    }
    assert [doc.page_content for doc in result["documents"]] == ["beta"]
    assert result["documents"][0].metadata["rerank_score"] == 0.95


def test_make_crag_rerank_node_fails_open(monkeypatch):
    messages = []

    monkeypatch.setattr(builtins, "print", messages.append)

    def broken_reranker(question, docs, top_k):
        raise RuntimeError("boom")

    node = crag_nodes.make_crag_rerank_node(broken_reranker, top_k=1)
    docs = [Document(page_content="alpha", metadata={"source": "first"})]

    result = node({"question": "question", "documents": docs})

    assert result["documents"] == docs
    assert any("rerank" in message.lower() for message in messages)


def test_make_crag_places_rerank_between_retrieve_and_grade():
    calls = []

    def make_retriever_node(_retriever):
        def node(_state):
            calls.append("retrieve")
            return {"documents": [Document(page_content="alpha", metadata={})]}

        return node

    def make_rerank_node(_reranker, top_k):
        assert top_k == 2

        def node(state):
            calls.append("rerank")
            return state

        return node

    def grader(_state):
        calls.append("grade")
        return {"grade": "relevant"}

    def generator(_state):
        calls.append("generate")
        return {"answer": "done", "context": "ctx"}

    def quality_check(_state):
        calls.append("quality_check")
        return {"hallucination_grade": "yes", "answer_grade": "yes"}

    graph = crag.make_crag(
        retriever_obj=object(),
        make_retriever_node=make_retriever_node,
        make_rerank_node=make_rerank_node,
        reranker=lambda question, docs, top_k: docs,
        rerank_top_k=2,
        grader=grader,
        rewriter=lambda state: state,
        generator=generator,
        quality_check=quality_check,
        fallback=lambda state: {"answer": "fallback"},
    )

    result = graph.invoke({"question": "question"})

    assert calls[:3] == ["retrieve", "rerank", "grade"]
    assert result["answer"] == "done"
