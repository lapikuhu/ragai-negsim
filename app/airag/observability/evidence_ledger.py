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
    """
    Create an empty ledger structure.
    Args:
        None
    Returns:
        dict: An empty ledger structure with default keys and values.
    """
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
    """
    Append a pipeline step to the ledger.
    Args:
        ledger (dict[str, Any] | None): The current ledger or None.
        name (str): The name of the pipeline step.
        status (str): The status of the pipeline step.
        detail (dict[str, Any] | None): Additional details for the step.
    Returns:
        dict[str, Any]: The updated ledger with the new pipeline step.
    """
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
    """
    Append a quality check to the ledger.
    Args:
        ledger (dict[str, Any] | None): The current ledger or None.
        name (str): The name of the quality check.
        verdict (str): The verdict of the quality check.
        reasoning (str): The reasoning for the verdict.
    Returns:
        dict[str, Any]: The updated ledger with the new quality check.
    """
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
    """
    Create a source card from a document.
    Args:
        doc (Document): The document to create the source card from.
        rank (int): The rank of the document.
    Returns:
        dict[str, Any]: The source card with metadata and excerpt.
    """
    metadata = dict(doc.metadata or {})
    card = {"rank": rank}
    for key in SAFE_SOURCE_METADATA:
        if key in metadata:
            card[key] = metadata[key]
    content = str(doc.page_content or "").strip()
    card["excerpt"] = content[:500]
    return card


def source_cards_from_documents(documents: list[Document]) -> list[dict[str, Any]]:
    """
    Create source cards from a list of documents.
    Args:
        documents (list[Document]): The list of documents to create source cards from.
    Returns:
        list[dict[str, Any]]: A list of source cards.
    """
    return [document_source_card(doc, rank=index + 1) for index, doc in enumerate(documents)]


def _source_list(value: Any) -> list[dict[str, Any]]:
    """
    Convert a value to a list of dictionaries if possible.
    Args:
        value (Any): The value to convert.
    Returns:
        list[dict[str, Any]]: A list of dictionaries.
    """
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def extract_source_cards(ledger: dict[str, Any] | None) -> list[dict[str, Any]]:
    """
    Extract source cards from a direct ledger or a nested CRAG ledger.
    Args:
        ledger (dict[str, Any] | None): The ledger to extract source 
            cards from.
    Returns:
        list[dict[str, Any]]: A list of source cards extracted from the 
        ledger.
    """
    if not isinstance(ledger, dict):
        return []

    direct_sources = _source_list(ledger.get("sources"))
    if direct_sources:
        return direct_sources

    for nested_key in ("crag", "graphrag"):
        nested = ledger.get(nested_key)
        if isinstance(nested, dict):
            sources = _source_list(nested.get("sources"))
            if sources:
                return sources
    return []


def set_sources(
    ledger: dict[str, Any] | None,
    documents: list[Document],
) -> dict[str, Any]:
    """
    Set the sources in the ledger from a list of documents.
    Args:
        ledger (dict[str, Any] | None): The current ledger or None.
        documents (list[Document]): The list of documents to set as sources.
    Returns:
        dict[str, Any]: The updated ledger with the new sources.
    """
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
    """
    Build a ledger record for an agent in a simulation.
    Args:
        simulation_id (int): The ID of the simulation.
        turn_index (int): The index of the turn in the simulation.
        agent_name (str): The name of the agent.
        sequence (int): The sequence number of the ledger record.
        ledger (dict[str, Any] | None): The current ledger or None.
        output_summary (dict[str, Any] | None): A summary of the output.
        token_usage (dict[str, Any] | None): Token usage information.
    Returns:
        SimulationEvidenceLedgerCreate: The constructed ledger record 
        for the agent.
    """
    value = deepcopy(ledger or ledger_empty())
    sources = extract_source_cards(value)
    return SimulationEvidenceLedgerCreate(
        simulation_id=simulation_id,
        turn_index=turn_index,
        agent_name=agent_name,
        sequence=sequence,
        visibility_level="debug",
        pipeline=value.get("pipeline", {"steps": []}),
        sources=sources,
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
    """
    Update the agent's ledger in the state with a new pipeline step and 
    optional output summary.
    Args:
        state (dict[str, Any]): The current state containing the evidence 
            ledger.
        agent_name (str): The name of the agent whose ledger is being updated.
        step_name (str): The name of the pipeline step to append.
        status (str): The status of the pipeline step.
        detail (dict[str, Any] | None): Additional details for the step.
        output_summary (dict[str, Any] | None): Optional summary of the 
            output to include in the agent's ledger.
        extra (dict[str, Any] | None): Additional key-value pairs to update 
            in the agent's ledger.
    """
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
