from copy import deepcopy
from typing import Any

from langchain_core.documents import Document

from app.schemas.evidence_ledger_schemas import SimulationEvidenceLedgerCreate


SAFE_SOURCE_METADATA = (
    "document_chunk_id",
    "raw_document_id",
    "chunk_index",
    "source",
    "score",
    "rerank_score",
    "retrieval_strategy",
    "retrieval_mode",
    "graph_id",
    "graph_generation",
    "evidence_path",
)


def ledger_empty() -> dict[str, Any]:
    return {
        "pipeline": {"steps": []},
        "sources": [],
        "quality_checks": [],
        "model": {},
        "raw_debug": {},
    }


def append_pipeline_step(
    ledger: dict[str, Any] | None,
    *,
    name: str,
    status: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = deepcopy(ledger or ledger_empty())
    updated.setdefault("pipeline", {}).setdefault("steps", []).append(
        {
            "name": name,
            "status": status,
            "detail": detail or {},
        }
    )
    return updated


def append_quality_check(
    ledger: dict[str, Any] | None,
    *,
    name: str,
    verdict: str,
    reasoning: str = "",
) -> dict[str, Any]:
    updated = deepcopy(ledger or ledger_empty())
    updated.setdefault("quality_checks", []).append(
        {
            "name": name,
            "verdict": verdict,
            "reasoning": reasoning,
        }
    )
    return updated


def document_source_card(doc: Document, *, rank: int) -> dict[str, Any]:
    metadata = dict(doc.metadata or {})
    card = {"rank": rank}
    for key in SAFE_SOURCE_METADATA:
        if key in metadata:
            card[key] = metadata[key]
    content = str(doc.page_content or "").strip()
    card["excerpt"] = content[:500]
    return card


def source_cards_from_documents(documents: list[Document]) -> list[dict[str, Any]]:
    return [document_source_card(doc, rank=index + 1) for index, doc in enumerate(documents)]


def set_sources(
    ledger: dict[str, Any] | None,
    documents: list[Document],
) -> dict[str, Any]:
    updated = deepcopy(ledger or ledger_empty())
    updated["sources"] = source_cards_from_documents(documents)
    return updated


def build_agent_ledger_record(
    *,
    simulation_id: int,
    turn_index: int,
    agent_name: str,
    sequence: int,
    ledger: dict[str, Any] | None,
    output_summary: dict[str, Any] | None = None,
    token_usage: dict[str, Any] | None = None,
) -> SimulationEvidenceLedgerCreate:
    value = deepcopy(ledger or ledger_empty())
    return SimulationEvidenceLedgerCreate(
        simulation_id=simulation_id,
        turn_index=turn_index,
        agent_name=agent_name,
        sequence=sequence,
        visibility_level="debug",
        pipeline=value.get("pipeline", {"steps": []}),
        sources=value.get("sources", []),
        quality_checks=value.get("quality_checks", []),
        model=value.get("model", {}),
        token_usage=token_usage or {},
        output_summary=output_summary or {},
        raw_debug=value.get("raw_debug", {}),
    )


def update_agent_ledger(
    state: dict[str, Any],
    *,
    agent_name: str,
    step_name: str,
    status: str,
    detail: dict[str, Any] | None = None,
    output_summary: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ledger = dict(state.get("evidence_ledger") or {})
    agent_ledger = append_pipeline_step(
        ledger.get(agent_name),
        name=step_name,
        status=status,
        detail=detail,
    )
    if output_summary is not None:
        agent_ledger["output_summary"] = output_summary
    if extra:
        agent_ledger.update(extra)
    ledger[agent_name] = agent_ledger
    return ledger
