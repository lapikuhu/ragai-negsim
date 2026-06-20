import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

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


def log_step(status: str, message: str) -> None:
    """
    Helper to display the status of a seeding step in a consistent format.
    Args:
        status (str): The status of the step, e.g., "created", "skipped", 
            "failed".
        message (str): A descriptive message about the step.
    """
    print(f"[{status}] {message}")


async def rollback_and_log(session: AsyncSession, label: str, exc: Exception) -> None:
    """
    Rollback the current transaction and log the failure.
    Args:
        session (AsyncSession): The database session to rollback.
        label (str): A label describing the operation that failed.
        exc (Exception): The exception that caused the failure.
    """
    await session.rollback()
    log_step("failed", f"{label}: {exc}")


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
) -> None:
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
        return

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
        await rollback_and_log(session, f"user {username}", exc)
        return

    log_step("created", f"user {username}")


async def seed_scenario(
    session: AsyncSession,
    admin_user,
    *,
    name: str,
    description: str,
) -> None:
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
        return

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
        await rollback_and_log(session, f"scenario {name}", exc)
        return

    log_step("created", f"scenario {name}")


async def seed_persona(
    session: AsyncSession,
    admin_user,
    *,
    name: str,
    description: str,
) -> None:
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
        return

    try:
        await counterpart_personas_service.create_counterpart_persona_srvc(
            CounterpartPersonaCreateRequest(name=name, description=description),
            session,
            admin_user,
        )
    except Exception as exc:
        await rollback_and_log(session, f"persona {name}", exc)
        return

    log_step("created", f"persona {name}")


async def seed_chunking_profile(
    session: AsyncSession,
    *,
    name: str,
    strategy: str,
) -> None:
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
        return

    try:
        await chunking_profiles_service.create_chunking_profile_srvc(
            ChunkingProfileCreate(name=name, strategy=strategy, config={}),
            session,
        )
    except Exception as exc:
        await rollback_and_log(session, f"chunking profile {name}", exc)
        return

    log_step("created", f"chunking profile {name}")


async def seed_vector_store(session: AsyncSession, vector_store_data: dict[str, Any]) -> None:
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
        return

    try:
        await vector_stores_service.create_vector_store_srvc(
            VectorStoreCreate(**vector_store_data),
            session,
        )
    except Exception as exc:
        await rollback_and_log(session, f"vector store {vector_store_data['name']}", exc)
        return

    log_step("created", f"vector store {vector_store_data['name']}")


async def run_seed_steps(
    steps: list[Callable[[], Awaitable[None]]],
) -> None:
    """
    Run a series of seeding steps sequentially.
    Args:
        steps (list[Callable[[], Awaitable[None]]]): A list of asynchronous functions
            representing the seeding steps to run.
    Returns:
        None
    """
    for step in steps:
        await step()


async def seed_all(session: AsyncSession) -> None:
    log_step("started", "seed run")
    admin_user = await ensure_admin_user(session)

    await run_seed_steps(
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
        ]
    )
    log_step("completed", "seed run")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed_all(session)


if __name__ == "__main__":
    asyncio.run(main())
