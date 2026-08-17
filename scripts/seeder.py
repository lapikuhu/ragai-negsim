import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from pathlib import Path
from fastapi import UploadFile


try:
    from scripts.bootstrap import ensure_project_root_on_path
except ModuleNotFoundError:
    from bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_chat_model
from app.db.db import AsyncSessionLocal, create_admin_if_not_exists, seed_roles_if_not_exist
from app.repositories import (
    chunking_profiles_repo,
    counterpart_personas_repo,
    scenarios_repo,
    users_repo,
    vector_stores_repo,
)
from app.schemas.chunking_profiles_schemas import ChunkingProfileCreate
from app.schemas.counterpart_personas_schemas import CounterpartPersonaCreateRequest
from app.schemas.scenarios_schemas import ScenarioContextGenerateRequest, ScenarioCreateRequest
from app.schemas.users_schemas import UserCreate
from app.schemas.vector_stores_schemas import VectorStoreCreate
from app.services import (
    chunking_profiles_service,
    counterpart_personas_service,
    scenarios_service,
    users_service,
    vector_stores_service,
)
import app.services.corpus_service
import app.services.raw_documents_service
from app.services.corpus_service import CorpusCreate
try:
    from scripts.personas import PLACEHOLDER_PERSONAS
    from scripts.scenarios import PLACEHOLDER_SCENARIOS
except ModuleNotFoundError:
    from personas import PLACEHOLDER_PERSONAS
    from scenarios import PLACEHOLDER_SCENARIOS

CHUNKING_PROFILES = [
    {"name": "Recursive", "strategy": "recursive"},
    {"name": "Semantic", "strategy": "semantic"},
    {"name": "Hybrid", "strategy": "hybrid"},
]

VECTOR_STORES = [
    {
        "name": "ChromaVectorStoreDim384",
        "backend": "chroma",
        "embedding_model": "mini-l6-v2",
        "collection_name": "negotiation_collection_384",
        "path": "./chroma_db/dim384",
    },
    {
        "name": "FAISSVectorStoreDim768",
        "backend": "faiss",
        "embedding_model": "bge-base",
        "path": "./faiss_db/dim768",
    },
    {
        "name": "PGVectorStoreDim1536",
        "backend": "pgvector",
        "embedding_model": "text-embedding-3-small",
        "table_name": "negotiation_collection_1536",
    },
]

DEMO_DOCS_FOLDER = "./demo_docs"


def log_step(status: str, message: str) -> None:
    """
    Helper to display the status of a seeding step in a consistent format.
    Args:
        status (str): The status of the step, e.g., "created", "skipped", 
            "failed".
        message (str): A descriptive message about the step.
    """
    print(f"[{status}] {message}")


async def rollback_and_log(session: AsyncSession, label: str, exc: Exception) -> str:
    """
    Rollback the current transaction and log the failure.
    Args:
        session (AsyncSession): The database session to rollback.
        label (str): A label describing the operation that failed.
        exc (Exception): The exception that caused the failure.
    """
    await session.rollback()
    log_step("failed", f"{label}: {exc}")
    return label


async def ensure_admin_user(session: AsyncSession):
    """
    Ensure that the admin user exists in the database.
    Args:
        session (AsyncSession): The database session to use for the operation.
    Returns:
        The admin user object.
    Raises:
        RuntimeError: If the configured admin user was not found after setup.
    """
    await seed_roles_if_not_exist()
    await create_admin_if_not_exists()
    admin_user = await users_repo.get_user_by_username(settings.ADMIN_USERNAME, session)
    if admin_user is None:
        raise RuntimeError(
            f"Configured admin user '{settings.ADMIN_USERNAME}' was not found after setup"
        )
    log_step("ready", f"admin user {admin_user.username}")
    return admin_user


async def seed_user(
    session: AsyncSession,
    admin_user,
    *,
    username: str,
    password: str,
    role_name: str,
) -> str | None:
    """
    Seed a user in the database.
    Args:
        session (AsyncSession): The database session to use for the operation.
        admin_user: The admin user object.
        username (str): The username of the user to seed.
        password (str): The password of the user to seed.
        role_name (str): The role name of the user to seed.
    Returns:
        None
    """
    existing_user = await users_repo.get_user_by_username(username, session)
    if existing_user is not None:
        log_step("skipped", f"user {username} already exists")
        return None

    role = await users_repo.get_role_by_name(role_name, session)
    if role is None or role.id is None:
        raise RuntimeError(f"Role '{role_name}' is not available")

    try:
        await users_service.create_user_service(
            UserCreate(username=username, password=password, role_ids=[role.id]),
            session,
            admin_user,
        )
    except Exception as exc:
        return await rollback_and_log(session, f"user {username}", exc)

    log_step("created", f"user {username}")
    return None


async def seed_scenario(
    session: AsyncSession,
    admin_user,
    *,
    name: str,
    description: str,
) -> str | None:
    """
    Seed a scenario in the database.
    Args:
        session (AsyncSession): The database session to use for the operation.
        admin_user: The admin user object.
        name (str): The name of the scenario to seed.
        description (str): The description of the scenario to seed.
    Returns:
        None
    """
    existing_scenario = await scenarios_repo.get_scenario_by_name(name, session)
    if existing_scenario is not None:
        log_step("skipped", f"scenario {name} already exists")
        return None

    try:
        model = get_chat_model(provider="openai", model_name="gpt-4o-mini", temperature=0.0)
        generated_context = await scenarios_service.generate_scenario_context_srvc(
            ScenarioContextGenerateRequest(name=name, description=description),
            model,
        )
        await scenarios_service.create_scenario_srvc(
            ScenarioCreateRequest(
                name=name,
                description=description,
                public_context=generated_context.public_context,
                side_a_private_context=generated_context.side_a_private_context,
                side_b_private_context=generated_context.side_b_private_context,
                side_a_summary=generated_context.side_a_summary,
                side_b_summary=generated_context.side_b_summary,
            ),
            session,
            admin_user,
        )
    except Exception as exc:
        return await rollback_and_log(session, f"scenario {name}", exc)

    log_step("created", f"scenario {name}")
    return None


async def seed_load_docs(session: AsyncSession, admin_user) -> str | None:
    """
    Load documents in the database from the demo docs folder.
    Args:
        session (AsyncSession): The database session to use for the operation.
        admin_user: The admin user object.
    Returns:
        None
    """
    from app.services.raw_documents_service import create_uploaded_raw_document_srvc

    demo_docs_path = Path(DEMO_DOCS_FOLDER)
    if not demo_docs_path.exists():
        log_step("skipped", f"demo docs folder {DEMO_DOCS_FOLDER} does not exist")
        return None
    raw_docs_path = Path(settings.RAW_DOCS_DIR)
    demo_doc_name = "demo_doc_"
    demo_doc_title = "demo_title_"
    demo_doc_author = "demo_author_"
    demo_doc_description = "demo_description_"
    demo_doc_count = 0
    for file_path in demo_docs_path.iterdir():
        if not file_path.is_file():
            continue
        stored_file_path = raw_docs_path / file_path.name
        if stored_file_path.exists():
            log_step("skipped", f"document {file_path.name} already exists in {raw_docs_path}")
            continue
        demo_doc_count += 1
        demo_doc_name_full = f"{demo_doc_name}{demo_doc_count}"
        demo_doc_description_full = f"{demo_doc_description}{demo_doc_count}"
        demo_doc_title_full = f"{demo_doc_title}{demo_doc_count}"
        try:
            with file_path.open("rb") as file_handle:
                upload = UploadFile(file=file_handle, filename=file_path.name)
                await create_uploaded_raw_document_srvc(
                    name=demo_doc_name_full,
                    description=demo_doc_description_full,
                    document_title=demo_doc_title_full,
                    document_author=demo_doc_author,
                    corpus_ids=[],
                    upload=upload,
                    document_year=2026,
                    session=session,
                    current_user=admin_user,
                )
                log_step("created", f"document {file_path.name} loaded")
        except Exception as exc:
            return await rollback_and_log(session, f"document {file_path.name}", exc)
    return None

async def seed_corpus(session: AsyncSession, 
                      admin_user, *, 
                      name: str, 
                      description: str) -> str | None:
    """
    Seed a corpus in the database. If the db already has any corpora, this
    function will skip seeding to avoid duplicates.
    Args:
        session (AsyncSession): The database session to use for the operation.
        admin_user: The admin user object.
        name (str): The name of the corpus to seed.
        description (str): The description of the corpus to seed.
    Returns:
        None
    """

    # Check if any corpus exists
    try:
        existing_corpus = await app.services.corpus_service.list_corpora_srvc(session=session, limit=1)
        if existing_corpus:
            log_step("skipped", f"at least one corpus already exists")
            return None
    except Exception as exc:
        return await rollback_and_log(session, f"corpus {name}", exc)

    # If no existing corpus, create a new one
    # Get the list of raw document IDs to associate with the new corpus
    raw_documents = await app.services.raw_documents_service.list_raw_documents_srvc(session=session, limit=20)
    raw_document_ids = [doc.id for doc in raw_documents]
    corpus_data = CorpusCreate(name=name, description=description, 
                               raw_document_ids=raw_document_ids)
    try:
        await app.services.corpus_service.create_corpus_srvc(
            corpus_data=corpus_data,
            session=session,
            current_user=admin_user,
        )
        log_step("created", f"corpus {name}")
    except Exception as exc:
        return await rollback_and_log(session, f"corpus {name}", exc)
    return None

async def seed_persona(
    session: AsyncSession,
    admin_user,
    *,
    name: str,
    description: str,
) -> str | None:
    """
    Seed a persona in the database.
    Args:
        session (AsyncSession): The database session to use for the operation.
        admin_user: The admin user object.
        name (str): The name of the persona to seed.
        description (str): The description of the persona to seed.
    Returns:
        None
    """
    existing_persona = await counterpart_personas_repo.get_counterpart_persona_by_name(
        name,
        session,
    )
    if existing_persona is not None:
        log_step("skipped", f"persona {name} already exists")
        return None

    try:
        await counterpart_personas_service.create_counterpart_persona_srvc(
            CounterpartPersonaCreateRequest(name=name, description=description),
            session,
            admin_user,
        )
    except Exception as exc:
        return await rollback_and_log(session, f"persona {name}", exc)

    log_step("created", f"persona {name}")
    return None


async def seed_chunking_profile(
    session: AsyncSession,
    *,
    name: str,
    strategy: str,
) -> str | None:
    """
    Seed a chunking profile in the database.
    Args:
        session (AsyncSession): The database session to use for the operation.
        name (str): The name of the chunking profile to seed.
        strategy (str): The strategy of the chunking profile to seed.
    Returns:
        None
    """
    existing_profile = await chunking_profiles_repo.get_chunking_profile_by_name(name, session)
    if existing_profile is not None:
        log_step("skipped", f"chunking profile {name} already exists")
        return None

    try:
        await chunking_profiles_service.create_chunking_profile_srvc(
            ChunkingProfileCreate(name=name, strategy=strategy, config={}),
            session,
        )
    except Exception as exc:
        return await rollback_and_log(session, f"chunking profile {name}", exc)

    log_step("created", f"chunking profile {name}")
    return None


async def seed_vector_store(session: AsyncSession, vector_store_data: dict[str, Any]) -> str | None:
    """
    Seed a vector store in the database.
    Args:
        session (AsyncSession): The database session to use for the operation.
        vector_store_data (dict): A dictionary containing the vector store data to seed.
    Returns:
        None
    """
    existing_store = await vector_stores_repo.get_vector_store_by_name(
        vector_store_data["name"],
        session,
    )
    if existing_store is not None:
        log_step("skipped", f"vector store {vector_store_data['name']} already exists")
        return None

    try:
        await vector_stores_service.create_vector_store_srvc(
            VectorStoreCreate(**vector_store_data),
            session,
        )
    except Exception as exc:
        return await rollback_and_log(session, f"vector store {vector_store_data['name']}", exc)

    log_step("created", f"vector store {vector_store_data['name']}")
    return None


async def run_seed_steps(
    steps: list[Callable[[], Awaitable[str | None]]],
) -> list[str]:
    """
    Run a series of seeding steps sequentially.
    Args:
        steps (list[Callable[[], Awaitable[str | None]]]): A list of asynchronous functions
            representing the seeding steps to run.
    Returns:
        The labels of seed operations that failed after rolling back.
    """
    failures = []
    for step in steps:
        failure = await step()
        if failure is not None:
            failures.append(failure)
    return failures


async def seed_all(session: AsyncSession) -> None:
    log_step("started", "seed run")
    admin_user = await ensure_admin_user(session)

    failures = await run_seed_steps(
        [
            lambda: seed_user(
                session,
                admin_user,
                username="student1",
                password="student1",
                role_name="student",
            ),
            lambda: seed_user(
                session,
                admin_user,
                username="teacher1",
                password="teacher1",
                role_name="teacher",
            ),
            *[
                (
                    lambda scenario=item: seed_scenario(
                        session,
                        admin_user,
                        name=scenario["name"],
                        description=scenario["description"],
                    )
                )
                for item in PLACEHOLDER_SCENARIOS
            ],
            *[
                (
                    lambda persona=item: seed_persona(
                        session,
                        admin_user,
                        name=persona["name"],
                        description=persona["description"],
                    )
                )
                for item in PLACEHOLDER_PERSONAS
            ],
            *[
                (
                    lambda profile=item: seed_chunking_profile(
                        session,
                        name=profile["name"],
                        strategy=profile["strategy"],
                    )
                )
                for item in CHUNKING_PROFILES
            ],
            *[
                (lambda vector_store=item: seed_vector_store(session, vector_store))
                for item in VECTOR_STORES
            ],
            lambda: seed_load_docs(session, admin_user),
            lambda: seed_corpus(
                session,
                admin_user,
                name="demo_corpus_1",
                description="Demo corpus from the demo documents",
            ),
        ]
    )
    if failures:
        raise RuntimeError(f"{len(failures)} seeding operation failed: {', '.join(failures)}")
    log_step("completed", "seed run")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed_all(session)


if __name__ == "__main__":
    asyncio.run(main())
