import pytest

from app.airag.embeddings.embeddings import SUPPORTED_EMBEDDING_MODELS
from app.airag.knowledge_graph import k_graph


class FakeEmbeddings:
    def embed_query(self, query: str) -> list[float]:
        return [float(len(query))]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]


@pytest.mark.parametrize("model_name", sorted(SUPPORTED_EMBEDDING_MODELS))
def test_create_graph_embedding_model_accepts_supported_models(monkeypatch, model_name):
    calls = []

    def fake_choose_embedding_model(selected_model: str):
        calls.append(selected_model)
        if selected_model not in SUPPORTED_EMBEDDING_MODELS:
            raise ValueError("unsupported")
        return FakeEmbeddings(), {"dimensionality": 1}

    monkeypatch.setattr(k_graph, "choose_embedding_model", fake_choose_embedding_model)

    embedding_model = k_graph.create_graph_embedding_model(
        {"embedding_model": model_name}
    )

    assert calls == [model_name]
    assert isinstance(embedding_model, k_graph.LangChainEmbeddingAdapter)
    assert embedding_model.get_query_embedding("abc") == [3.0]
    assert embedding_model.get_text_embedding("abcd") == [4.0]


def test_create_graph_embedding_model_rejects_unknown_non_legacy_model(monkeypatch):
    def fake_choose_embedding_model(_selected_model: str):
        raise ValueError("unsupported")

    monkeypatch.setattr(k_graph, "choose_embedding_model", fake_choose_embedding_model)

    with pytest.raises(ValueError, match="Unsupported embedding model: unknown-model"):
        k_graph.create_graph_embedding_model({"embedding_model": "unknown-model"})
