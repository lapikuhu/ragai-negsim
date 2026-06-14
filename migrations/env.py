from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from app.core.config import settings
from app.models import chunking_profiles  # noqa: F401
from app.models import corpus  # noqa: F401
from app.models import corpus_indices  # noqa: F401
from app.models import counterpart_personas  # noqa: F401
from app.models import document_chunks  # noqa: F401
from app.models import indexed_chunks  # noqa: F401
from app.models import indexing_job_warnings  # noqa: F401
from app.models import indexing_jobs  # noqa: F401
from app.models import knowledge_graph_build_jobs  # noqa: F401
from app.models import knowledge_graph_indices  # noqa: F401
from app.models import prompts  # noqa: F401
from app.models import raw_documents  # noqa: F401
from app.models import scenarios  # noqa: F401
from app.models import sessions  # noqa: F401
from app.models import simulations  # noqa: F401
from app.models import user_roles  # noqa: F401
from app.models import users  # noqa: F401
from app.models import vector_stores  # noqa: F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _sync_database_url() -> str:
    """
    Alembic runs against a synchronous SQLAlchemy URL.
    """
    return settings.ASYNC_DATABASE_URL.replace("+asyncpg", "+psycopg")


config.set_main_option("sqlalchemy.url", _sync_database_url())

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
