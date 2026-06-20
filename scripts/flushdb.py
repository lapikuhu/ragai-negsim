try:
    from scripts.bootstrap import ensure_project_root_on_path
except ModuleNotFoundError:
    from bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)

# Script to delete all data from the database. Use with caution!
from app.db.db import engine
from sqlmodel import SQLModel
from app.models import (  # noqa: F401
    chunking_profiles,
    corpus,
    corpus_indices,
    counterpart_personas,
    document_chunks,
    indexed_chunks,
    indexing_job_warnings,
    indexing_jobs,
    knowledge_graph_build_jobs,
    knowledge_graph_indices,
    prompts,
    rag_profiles,
    raw_documents,
    scenarios,
    sessions,
    simulation_evidence_ledgers,
    simulations,
    user_roles,
    users,
    vector_stores,
)

async def flush_db() -> None:
    """
    Flush the database by dropping all tables and recreating them.
    Use with caution as this will delete all data.
    Args:
        None
    Returns:
        None
    """
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
if __name__ == "__main__":
    import asyncio
    asyncio.run(flush_db())
