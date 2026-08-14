"""
Backend helper service for resolving compatible indices when building a
 hybrid RAG index for a simulation.
 """
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.airag.rag_profiles.definitions import (
    get_crag_retrieval_mode,
    normalize_rag_profile_config,
)
from app.repositories import (
    corpus_bm25_indices_repo,
    corpus_indices_repo,
    corpus_repo,
    indexed_chunks_repo,
    rag_profiles_repo,
)
from app.repositories.corpus_bm25_indices_repo import document_chunk_ids_checksum
from app.schemas.simulations_schemas import (
    SimulationRetrievalCompatiblePair,
    SimulationRetrievalIndexOption,
    SimulationRetrievalOptionsResponse,
)


def ensure_hybrid_indices_compatible(
    *,
    corpus_id: int,
    corpus_index: Any,
    bm25_index: Any,
    dense_chunk_ids: list[int],
) -> None:
    """
    Enforce the exact persisted-artifact contract for one hybrid pair.
    Corpora can have multiple dense and BM25 indices, but not all of them
    can be paired together to form a hybrid RAG index. This function checks 
    that the two indices are compatible for hybrid use, and raises a 
    ValueError if they are not.

    Args:
        corpus_id: The ID of the corpus.
        corpus_index: The dense index object.
        bm25_index: The BM25 index object.
        dense_chunk_ids: The list of chunk IDs for the dense index.
    Raises:
        ValueError: If the indices are not compatible for hybrid use.
    """
    if corpus_index.status != "built" or bm25_index.status != "built":
        raise ValueError("Hybrid indexes must both be built")
    if corpus_index.corpus_id != corpus_id or bm25_index.corpus_id != corpus_id:
        raise ValueError("Hybrid indexes must use the same corpus")
    if bm25_index.compressed_artifact_checksum is None:
        raise ValueError("Built BM25 index is missing its artifact checksum")
    if corpus_index.chunking_profile_id != bm25_index.chunking_profile_id:
        raise ValueError("Hybrid indexes must use the same chunking profile")
    if len(dense_chunk_ids) != bm25_index.document_count:
        raise ValueError("Hybrid indexes must have the same document count")
    # Even if the chunks are identical, we actually want the same rows. Technical
    # debt, instead of checking content and chunk struct checksum, we check 
    # the checksum of the chunk IDs.
    if (
        document_chunk_ids_checksum(dense_chunk_ids)
        != bm25_index.document_chunk_ids_checksum
    ):
        raise ValueError("Hybrid indexes must contain the same chunk set")


def _index_option(index: Any) -> SimulationRetrievalIndexOption:
    """
    Return a SimulationRetrievalIndexOption for the given index.

    Args:
        index: The index object.
    Returns:
        SimulationRetrievalIndexOption: The corresponding index option.
    """
    return SimulationRetrievalIndexOption(id=index.id, name=index.name)


async def get_simulation_retrieval_options_srvc(
    *,
    corpus_id: int,
    rag_profile_id: int,
    session: AsyncSession,
) -> SimulationRetrievalOptionsResponse:
    """
    Return profile-authoritative indices for a simulation's retrieval options.
    If the RAG profile is dense only, return all dense indices for the corpus. 
    If the RAG profile is BM25 only, return all BM25 indices for the corpus. 
    If the RAG profile is hybrid, return all compatible pairs of dense and BM25 
    indices for the corpus.

    Used to help frontend render the correct retrieval options.

    Args:
        corpus_id: The ID of the corpus.
        rag_profile_id: The ID of the RAG profile.
        session: The database session.
    Returns:
        SimulationRetrievalOptionsResponse: The retrieval options response.
    Raises:
        ValueError: If the corpus or RAG profile is not found, or if the 
        RAG profile is not a CRAG profile.
    """
    if await corpus_repo.get_corpus_by_id(corpus_id, session) is None:
        raise ValueError("Corpus not found")

    rag_profile = await rag_profiles_repo.get_rag_profile_by_id(
        rag_profile_id,
        session,
    )
    if rag_profile is None:
        raise ValueError("RAG profile not found")
    if rag_profile.strategy != "crag":
        raise ValueError("Retrieval options require a CRAG profile")

    config = normalize_rag_profile_config("crag", rag_profile.config or {})
    mode = get_crag_retrieval_mode(config["bm25_weight"])

    # Dense case: return all dense indices for the corpus
    if mode == "dense":
        dense_indices = await corpus_indices_repo.list_built_corpus_indices_for_corpus(
            corpus_id,
            session,
        )
        return SimulationRetrievalOptionsResponse(
            mode=mode,
            dense_indices=[_index_option(index) for index in dense_indices],
        )

    bm25_indices = (
        await corpus_bm25_indices_repo.list_built_corpus_bm25_index_metadata_for_corpus(
            corpus_id,
            session,
        )
    )
    usable_bm25_indices = [
        index
        for index in bm25_indices
        if index.compressed_artifact_checksum is not None
    ]
    # BM25 case: return all usable BM25 indices for the corpus
    if mode == "bm25":
        return SimulationRetrievalOptionsResponse(
            mode=mode,
            bm25_indices=[_index_option(index) for index in usable_bm25_indices],
        )

    dense_indices = await corpus_indices_repo.list_built_corpus_indices_for_corpus(
        corpus_id,
        session,
    )
    pairs: list[SimulationRetrievalCompatiblePair] = []
    pairable_dense_ids: set[int] = set()
    pairable_bm25_ids: set[int] = set()

    # Get all dense indices first, and check if any can be paired with any
    # BM25 index. If they can, add them to the compatible pairs list.
    for dense_index in dense_indices:
        dense_chunk_ids = (
            await indexed_chunks_repo.get_document_chunk_ids_by_corpus_index_id(
                dense_index.id,
                session,
            )
        )
        for bm25_index in usable_bm25_indices:
            try:
                ensure_hybrid_indices_compatible(
                    corpus_id=corpus_id,
                    corpus_index=dense_index,
                    bm25_index=bm25_index,
                    dense_chunk_ids=dense_chunk_ids,
                )
            except ValueError:
                continue
            pairs.append(
                SimulationRetrievalCompatiblePair(
                    corpus_index_id=dense_index.id,
                    bm25_index_id=bm25_index.id,
                )
            )
            pairable_dense_ids.add(dense_index.id)
            pairable_bm25_ids.add(bm25_index.id)

    return SimulationRetrievalOptionsResponse(
        mode=mode,
        dense_indices=[
            _index_option(index)
            for index in dense_indices
            if index.id in pairable_dense_ids
        ],
        bm25_indices=[
            _index_option(index)
            for index in usable_bm25_indices
            if index.id in pairable_bm25_ids
        ],
        compatible_pairs=pairs,
    )
