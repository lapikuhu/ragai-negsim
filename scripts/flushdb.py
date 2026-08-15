try:
    from scripts.bootstrap import ensure_project_root_on_path
except ModuleNotFoundError:
    from bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)

# Script to delete all data from the database. Use with caution!
from app.db.db import engine
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlmodel import SQLModel
from app.models import (  # noqa: F401
    chunking_profiles,
    corpus,
    corpus_bm25_indices,
    corpus_indices,
    counterpart_personas,
    document_chunks,
    indexed_chunks,
    full_corpus_index_pipe_job_warnings,
    full_corpus_index_pipe_jobs,
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


def _drop_model_tables(connection: Connection) -> None:
    """
    Drop model tables, using CASCADE for PostgreSQL foreign-key cycles.

    Args:
        connection (Connection): The database connection to use for 
        dropping tables.
    Returns:
        None
    """
    if connection.dialect.name != "postgresql":
        SQLModel.metadata.drop_all(connection)
        return

    preparer = connection.dialect.identifier_preparer
    table_names = ", ".join(
        preparer.format_table(table) for table in SQLModel.metadata.tables.values()
    )
    if table_names:
        connection.execute(text(f"DROP TABLE IF EXISTS {table_names} CASCADE"))

async def flush_db(create_all_option: bool = True) -> None:
    """
    Flush the database by dropping all tables and recreating them.
    Use with caution as this will delete all data.
    Args:
        create_all_option (bool): Whether to recreate all tables after flushing.
    Returns:
        None
    """
    # Small guardail to prevent accidental execution
    user_input = input("Are you sure you want to flush the database? This will delete all data. (yes/no): ")
    if user_input.lower() != "yes" and user_input.lower() != "y":
        print("Database flush aborted.")
        return
    async with engine.begin() as conn:
        await conn.run_sync(_drop_model_tables)
        if create_all_option:
            await conn.run_sync(SQLModel.metadata.create_all)
if __name__ == "__main__":
    import asyncio
    asyncio.run(flush_db(create_all_option=False))
