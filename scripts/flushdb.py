try:
    from scripts.bootstrap import ensure_project_root_on_path
except ModuleNotFoundError:
    from bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)

from app.core.config import settings
DATABASE_URL = settings.DATABASE_URL

# Script to delete all data from the database. Use with caution!
from app.db import engine
from app.models import Base

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
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
if __name__ == "__main__":
    import asyncio
    asyncio.run(flush_db())
