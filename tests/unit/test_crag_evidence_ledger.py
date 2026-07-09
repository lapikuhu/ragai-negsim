from langchain_core.documents import Document

from app.airag.chains.crag.crag_nodes import (
    make_crag_rerank_node,
    make_crag_retrieve_node,
    make_node_grade,
    make_node_quality_check,
    make_node_rewrite,
)


class StaticRetriever:
    def invoke(self, query):
        return [
            Document(
                page_content="Counteroffers should use objective standards.",
                metadata={"document_chunk_id": 11, "score": 0.5},
            )
        ]


class GradeVerdict:
    relevance = "relevant"
    reasoning = "The retrieved source discusses counteroffers."


class HallVerdict:
    grounded = "yes"
    reasoning = "All claims are supported."


class AnswerVerdict:
    addresses = "yes"


class StaticChain:
    def __init__(self, value):
        self.value = value

    def invoke(self, _payload, _config=None):
        return self.value


def test_retrieve_node_appends_sources_and_pipeline_event():
    node = make_crag_retrieve_node(StaticRetriever())

    result = node({"question": "How should I counteroffer?"})

    assert result["documents"][0].metadata["document_chunk_id"] == 11
    assert result["evidence_ledger"]["pipeline"]["steps"][0]["name"] == "retrieve"
    assert result["evidence_ledger"]["sources"][0]["document_chunk_id"] == 11


def test_rerank_node_records_order_and_scores():
    def reranker(_question, docs, _top_k):
        return [
            Document(
                page_content=docs[0].page_content,
                metadata={**docs[0].metadata, "rerank_score": 0.91},
            )
        ]

    node = make_crag_rerank_node(reranker, top_k=1)
    result = node(
        {
            "question": "How should I counteroffer?",
            "documents": [Document(page_content="A", metadata={"document_chunk_id": 1})],
        }
    )

    step = result["evidence_ledger"]["pipeline"]["steps"][0]
    assert step["name"] == "rerank"
    assert step["detail"]["top_k"] == 1
    assert result["evidence_ledger"]["sources"][0]["rerank_score"] == 0.91


def test_grade_rewrite_and_quality_nodes_record_checks():
    grade_node = make_node_grade(StaticChain(GradeVerdict()))
    grade = grade_node(
        {
            "question": "How should I counteroffer?",
            "documents": [Document(page_content="A", metadata={"document_chunk_id": 1})],
        }
    )
    assert grade["evidence_ledger"]["quality_checks"][0]["name"] == "document_relevance"

    rewrite_node = make_node_rewrite(StaticChain("better query"))
    rewrite = rewrite_node({"question": "bad query"})
    assert rewrite["rewritten"] == "better query"
    assert rewrite["evidence_ledger"]["pipeline"]["steps"][0]["name"] == "rewrite"

    quality_node = make_node_quality_check(StaticChain(HallVerdict()), StaticChain(AnswerVerdict()))
    quality = quality_node(
        {
            "question": "How should I counteroffer?",
            "answer": "Use objective standards.",
            "context": "Objective standards are useful.",
        }
    )
    assert [check["name"] for check in quality["evidence_ledger"]["quality_checks"]] == [
        "groundedness",
        "answer_relevance",
    ]
