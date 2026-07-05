from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.repositories import raw_documents_repo

# Dodgy
RAW_DOCUMENT_SOURCE_FIELDS = (
    ("raw_document_name", "name"),
    ("document_title", "document_title"),
    ("document_author", "document_author"),
    ("document_year", "document_year"),
)


async def enrich_source_cards_with_raw_document_metadata(
    sources: list[dict[str, Any]],
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """
    Enrich source cards with public raw-document metadata.
    Args:
        sources: A list of source cards, each containing a 
            'raw_document_id'.
        session: An active SQLAlchemy AsyncSession for database access.
    Returns:
        A list of source cards enriched with raw-document metadata.
    """
    raw_documents_by_id: dict[int, Any | None] = {}
    enriched: list[dict[str, Any]] = []

    for source in sources:
        card = dict(source)
        raw_document_id = card.get("raw_document_id")
        if isinstance(raw_document_id, int):
            if raw_document_id not in raw_documents_by_id:
                raw_documents_by_id[raw_document_id] = (
                    await raw_documents_repo.get_raw_document_by_id(
                        raw_document_id,
                        session,
                    )
                )
            raw_document = raw_documents_by_id.get(raw_document_id)
            if raw_document is not None:
                for card_key, attr_name in RAW_DOCUMENT_SOURCE_FIELDS:
                    value = getattr(raw_document, attr_name, None)
                    if value is not None and value != "":
                        card[card_key] = value
        enriched.append(card)
    return enriched
