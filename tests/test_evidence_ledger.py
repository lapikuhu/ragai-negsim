from langchain_core.documents import Document

from app.airag.observability.evidence_ledger import (
    append_pipeline_step,
    build_agent_ledger_record,
    document_source_card,
    extract_source_cards,
    ledger_empty,
)


def test_append_pipeline_step_is_non_mutating():
    ledger = ledger_empty()
    updated = append_pipeline_step(
        ledger,
        name="retrieve",
        status="success",
        detail={"query": "pricing tactics"},
    )

    assert ledger["pipeline"]["steps"] == []
    assert updated["pipeline"]["steps"] == [
        {"name": "retrieve", "status": "success", "detail": {"query": "pricing tactics"}}
    ]


def test_document_source_card_keeps_safe_metadata_and_excerpt():
    doc = Document(
        page_content="A strong counteroffer should anchor around your target and preserve BATNA.",
        metadata={
            "document_chunk_id": 7,
            "raw_document_id": 3,
            "chunk_index": 2,
            "source": "negotiation-notes.md",
            "score": 0.83,
            "rerank_score": 0.72,
            "private": "do not expose",
        },
    )

    card = document_source_card(doc, rank=1)

    assert card["rank"] == 1
    assert card["document_chunk_id"] == 7
    assert card["raw_document_id"] == 3
    assert card["chunk_index"] == 2
    assert card["source"] == "negotiation-notes.md"
    assert card["score"] == 0.83
    assert card["rerank_score"] == 0.72
    assert "counteroffer" in card["excerpt"]
    assert "private" not in card


def test_extract_source_cards_prefers_direct_sources_then_nested_crag_sources():
    direct = {"sources": [{"rank": 1, "source": "direct.pdf"}]}
    nested = {"crag": {"sources": [{"rank": 2, "source": "nested.pdf"}]}}

    assert extract_source_cards(direct) == [{"rank": 1, "source": "direct.pdf"}]
    assert extract_source_cards(nested) == [{"rank": 2, "source": "nested.pdf"}]


def test_build_agent_ledger_record_wraps_visibility_views():
    ledger = append_pipeline_step(
        ledger_empty(),
        name="generate",
        status="success",
        detail={"prompt": "hidden"},
    )

    record = build_agent_ledger_record(
        simulation_id=42,
        turn_index=3,
        agent_name="coach",
        sequence=4,
        ledger=ledger,
        output_summary={"kind": "coach_advice"},
        token_usage={"total_tokens": 99},
    )

    assert record.simulation_id == 42
    assert record.turn_index == 3
    assert record.agent_name == "coach"
    assert record.visibility_level == "debug"
    assert record.pipeline["steps"][0]["name"] == "generate"
    assert record.output_summary == {"kind": "coach_advice"}
    assert record.token_usage == {"total_tokens": 99}


def test_build_agent_ledger_record_promotes_nested_crag_sources():
    ledger = {
        "pipeline": {"steps": []},
        "crag": {
            "sources": [
                {
                    "rank": 1,
                    "raw_document_id": 3,
                    "document_chunk_id": 7,
                    "source": "negotiation-guide.pdf",
                }
            ]
        },
    }

    record = build_agent_ledger_record(
        simulation_id=42,
        turn_index=3,
        agent_name="coach",
        sequence=4,
        ledger=ledger,
    )

    assert record.sources == [
        {
            "rank": 1,
            "raw_document_id": 3,
            "document_chunk_id": 7,
            "source": "negotiation-guide.pdf",
        }
    ]
