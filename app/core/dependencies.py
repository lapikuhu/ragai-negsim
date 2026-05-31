from models.users import User
from services import auth
from db import AsyncSession, get_session
from security import oauth2_scheme
from typing import Annotated
from typing import Annotated, TypeAlias
from fastapi import Depends, HTTPException, Query
from functools import lru_cache
from collections.abc import Callable, Awaitable

from models.user_roles import Role, UserRoleLink
from sqlmodel import select
from config import Settings


# --------------- SETTINGS DEPENDENCY ---------------

@lru_cache
def get_settings() -> Settings:
    return Settings()
SettingsDep: TypeAlias = Annotated[Settings, Depends(get_settings)]

# --------------- DATABASE DEPENDENCY ---------------

SessionDep: TypeAlias = Annotated[AsyncSession, Depends(get_session)]
TokenDep: TypeAlias = Annotated[str, Depends(oauth2_scheme)]


async def get_current_user(token: TokenDep, session: SessionDep) -> User:
    """Get the current authenticated user based on the provided JWT token.
    Args:
        token (str): The JWT token extracted from the Authorization header.
        session (AsyncSession): The database session for querying user data.
    Returns:
        User: The authenticated user object.
    Raises:
        HTTPException: If the token is invalid or the user cannot be authenticated."""
    user = await auth.get_current_user(token, session)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return user

# -------------------------------------------------------------------- #

# --------------- ROLE-BASED ACCESS CONTROL DEPENDENCY --------------- #
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_role(role_name: str) -> Callable[[CurrentUserDep, SessionDep], Awaitable[User]]:
    """
    Factory function to create a dependency that checks if the current user 
    has a specific role.
    Args:
        role_name (str): The name of the required role (e.g., "admin", "teacher", "student").
    Returns:
        Callable: A dependency function that can be used with FastAPI's 
            Depends to enforce role-based access control.
    """
    async def dependency(current_user: CurrentUserDep, session: SessionDep) -> User:
        """
        Dependency function that checks if the current user has the specified 
        role.
        Args:
            current_user (User): The currently authenticated user.
            session (AsyncSession): The database session for querying user roles.
        Returns:
            User: The current user if they have the required role.
        Raises:
            HTTPException: If the user does not have the required role.
        """
        result = await session.exec(
            select(Role)
            .join(UserRoleLink, Role.id == UserRoleLink.role_id)
            .where(
                UserRoleLink.user_id == current_user.id,
                Role.name == role_name,
            )
        )

        if result.first() is None:
            raise HTTPException(
                status_code=403,
                detail=f"{role_name.capitalize()} role required",
            )

        return current_user

    return dependency


TeacherDep = Annotated[User, Depends(require_role("teacher"))]
AdminDep = Annotated[User, Depends(require_role("admin"))]
StudentDep = Annotated[User, Depends(require_role("student"))]

# --------------- PAGINATION DEPENDENCY ---------------

def pagination(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, int]:
    """Reusable pagination dependency.
    Args:
        skip (int): The number of items to skip.
        limit (int): The maximum number of items to return.
    Returns:
        dict: A dictionary containing the skip and limit values."""
    return {"skip": skip, "limit": limit}


Page = Annotated[dict, Depends(pagination)]
# -------------------------------------------------------------------- #
# --------------- CORPUS-RELATED DEPENDENCIES --------------- #
from models.corpus import Corpus

async def get_corpus_or_404(corpus_id: int, session: SessionDep) -> Corpus:
    """Dependency to retrieve a Corpus by ID or raise a 404 error if not found.
    Args:
        corpus_id (int): The ID of the Corpus to retrieve.
        session (AsyncSession): The database session for querying the Corpus.
    Returns:
        Corpus: The retrieved Corpus object.
    Raises:
        HTTPException: If the Corpus is not found.
    """
    corpus = await session.get(Corpus, corpus_id)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus not found")
    return corpus


CorpusDep = Annotated[Corpus, Depends(get_corpus_or_404)]

async def get_owned_corpus(
    corpus: CorpusDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Corpus:
    """
    Dependency to ensure that the current user is either the owner of the 
    corpus or has an admin role.
    Args:
        corpus (Corpus): The corpus being accessed.
        current_user (User): The currently authenticated user.
        session (AsyncSession): The database session for querying user roles.
    Returns:
        Corpus: The corpus if the user is the owner or an admin.
    Raises:
        HTTPException: If the user is neither the owner nor an admin.
    """
    if corpus.created_by_user_id == current_user.id:
        return corpus

    result = await session.exec(
        select(Role)
        .join(UserRoleLink, Role.id == UserRoleLink.role_id)
        .where(
            UserRoleLink.user_id == current_user.id,
            Role.name == "admin",
        )
    )
    if result.first() is None:
        raise HTTPException(status_code=403, detail="Corpus owner or admin required")

    return corpus


OwnedCorpusDep = Annotated[Corpus, Depends(get_owned_corpus)]
# -------------------------------------------------------------------- #

# ------------------ SIMULATION-RELATED DEPENDENCIES ----------------- #
from models.simulations import Simulation


async def get_simulation_or_404(simulation_id: int, session: SessionDep) -> Simulation:
    """
    Dependency to retrieve a Simulation by ID or raise a 404 error if not found.
    Args:
        simulation_id (int): The ID of the Simulation to retrieve.
        session (AsyncSession): The database session for querying the Simulation.
    Returns:
        Simulation: The retrieved Simulation object.
    Raises:
        HTTPException: If the Simulation is not found.
    """
    simulation = await session.get(Simulation, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return simulation


SimulationDep = Annotated[Simulation, Depends(get_simulation_or_404)]

async def get_accessible_simulation(
    simulation: SimulationDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Simulation:
    """
    Dependency to ensure that the current user has access to the simulation, either
    as an owner, participant, teacher, or admin.
    Args:
        simulation (Simulation): The simulation being accessed.
        current_user (User): The currently authenticated user.
        session (AsyncSession): The database session for querying user roles.
    Returns:
        Simulation: The simulation if the user has access.
    Raises:
        HTTPException: If the user does not have access.
    """
    user_id = current_user.id

    if user_id in {
        simulation.user_id_owner,
        simulation.user_id_participant,
        simulation.teacher_id,
    }:
        return simulation

    result = await session.exec(
        select(Role)
        .join(UserRoleLink, Role.id == UserRoleLink.role_id)
        .where(
            UserRoleLink.user_id == user_id,
            Role.name == "admin",
        )
    )

    if result.first() is None:
        raise HTTPException(status_code=403, detail="Simulation access required")

    return simulation


AccessibleSimulationDep = Annotated[Simulation, Depends(get_accessible_simulation)]

def require_simulation_status(*allowed_statuses: str):
    """
    Factory function to create a dependency that checks if a simulation is in 
    one of the allowed statuses.
    Args:
        simulation (Simulation): The simulation being checked.
    Returns:
        Simulation: The simulation if it is in one of the allowed statuses.
    Raises:
        HTTPException: If the simulation is not in one of the allowed statuses.
    """
    async def dependency(simulation: SimulationDep) -> Simulation:
        if simulation.status not in allowed_statuses:
            raise HTTPException(
                status_code=409,
                detail=f"Simulation must be one of: {', '.join(allowed_statuses)}",
            )
        return simulation

    return dependency


ActiveSimulationDep = Annotated[
    Simulation,
    Depends(require_simulation_status("active", "in_progress")),
]

# -------------------------------------------------------------------- #

# ------------------- PROMPTS-RELATED DEPENDENCIES ------------------- #

from models.prompts import Prompt


async def get_prompt_or_404(prompt_id: int, session: SessionDep) -> Prompt:
    """
    Dependency to retrieve a Prompt by ID or raise a 404 error if not found.
    Args:
        prompt_id (int): The ID of the Prompt to retrieve.
        session (AsyncSession): The database session for querying the Prompt.
    Returns:
        Prompt: The retrieved Prompt object.
    Raises:
        HTTPException: If the Prompt is not found.
    """
    prompt = await session.get(Prompt, prompt_id)
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt


PromptDep = Annotated[Prompt, Depends(get_prompt_or_404)]

async def get_editable_prompt(prompt: PromptDep, current_user: CurrentUserDep) -> Prompt:
    """
    Dependency to ensure that the current user can edit the prompt, which means
    they must be the owner and the prompt cannot be a system prompt.
    Args:
        prompt (Prompt): The prompt being accessed.
        current_user (User): The currently authenticated user.
    Returns:
        Prompt: The prompt if the user can edit it.
    Raises:
        HTTPException: If the user cannot edit the prompt.
    """
    if prompt.is_system:
        raise HTTPException(status_code=403, detail="System prompts cannot be edited here")

    if prompt.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Prompt owner required")

    return prompt


EditablePromptDep = Annotated[Prompt, Depends(get_editable_prompt)]

### ------------------- RAG-RELATED DEPENDENCIES ------------------- ###
# Embeddings

from langchain_core.embeddings import Embeddings
from airag.embeddings.embeddings import choose_embedding_model


def get_embedding_model(
    model_name: str = "mini-l6-v2",
) -> Embeddings:
    embedding_model, _ = choose_embedding_model(model_name)
    return embedding_model

EmbeddingModelDep = Annotated[Embeddings, Depends(get_embedding_model)]

# Metadata

def get_embedding_config(model_name: str = "mini-l6-v2") -> dict[str, int | str]:
    _, metadata = choose_embedding_model(model_name)
    return {
        "model_name": model_name,
        "dimensionality": metadata["dimensionality"],
    }


EmbeddingConfigDep = Annotated[dict[str, int | str], Depends(get_embedding_config)]

# LLM
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from airag.llm_models.llm_models import get_llm


def get_chat_model(
    provider: str = "openai",
    model_name: str = "gpt-4o-mini",
    temperature: float = 0.0,
) -> ChatOpenAI | ChatOllama:
    llm = get_llm(
        provider=provider,
        model_name=model_name,
        temperature=temperature,
    )

    if llm is None:
        raise HTTPException(status_code=503, detail="LLM provider unavailable")

    return llm


ChatModelDep = Annotated[ChatOpenAI | ChatOllama, Depends(get_chat_model)]

# Vector Store
from models.vector_stores import VectorStore

async def get_vector_store_record_or_404(
    vector_store_id: int,
    session: SessionDep,
) -> VectorStore:
    vector_store = await session.get(VectorStore, vector_store_id)

    if vector_store is None:
        raise HTTPException(status_code=404, detail="Vector store not found")

    return vector_store


VectorStoreRecordDep = Annotated[
    VectorStore,
    Depends(get_vector_store_record_or_404),
]

from airag.vector_stores.vector_stores import (
    instantiate_chroma_vector_store,
    load_faiss_vector_store,
)


async def get_runtime_vector_store(
    vector_store_record: VectorStoreRecordDep,
    embedding_model: EmbeddingModelDep,
):
    if vector_store_record.backend == "chroma":
        return instantiate_chroma_vector_store(
            embedding_model=embedding_model,
            collection_name=vector_store_record.collection_name or "negotiation_corpus",
            persist_directory=vector_store_record.path or "./chroma_db",
        )

    if vector_store_record.backend == "faiss":
        return load_faiss_vector_store(
            embeddings=embedding_model,
            path=vector_store_record.path or "./faiss_db",
        )

    raise HTTPException(
        status_code=400,
        detail=f"Unsupported vector store backend: {vector_store_record.backend}",
    )


RuntimeVectorStoreDep = Annotated[object, Depends(get_runtime_vector_store)]

# Corpus Index
from models.corpus_indices import CorpusIndex


async def get_corpus_index_or_404(
    corpus_index_id: int,
    session: SessionDep,
) -> CorpusIndex:
    corpus_index = await session.get(CorpusIndex, corpus_index_id)

    if corpus_index is None:
        raise HTTPException(status_code=404, detail="Corpus index not found")

    return corpus_index


CorpusIndexDep = Annotated[CorpusIndex, Depends(get_corpus_index_or_404)]

# Reranker
from sentence_transformers import CrossEncoder

@lru_cache
def get_cross_encoder() -> CrossEncoder:
    return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


CrossEncoderDep = Annotated[CrossEncoder, Depends(get_cross_encoder)]

# Retrieval Options
from pydantic import BaseModel


class RetrievalOptions(BaseModel):
    k: int = 4
    rerank: bool = True
    rerank_top_k: int = 3


def get_retrieval_options(
    k: int = Query(default=4, ge=1, le=20),
    rerank: bool = Query(default=True),
    rerank_top_k: int = Query(default=3, ge=1, le=20),
) -> RetrievalOptions:
    return RetrievalOptions(k=k, rerank=rerank, rerank_top_k=rerank_top_k)


RetrievalOptionsDep = Annotated[RetrievalOptions, Depends(get_retrieval_options)]

# Ingestion Options

class IngestionOptions(BaseModel):
    header_depth: int = 2
    dynamic_header_depth: bool = False
    chunk_size: int = 1000
    chunk_overlap: int = 200
    chunker: str = "recursive"


def get_ingestion_options(
    header_depth: int = Query(default=2, ge=1, le=6),
    dynamic_header_depth: bool = Query(default=False),
    chunk_size: int = Query(default=1000, ge=100, le=8000),
    chunk_overlap: int = Query(default=200, ge=0, le=2000),
    chunker: str = Query(default="recursive"),
) -> IngestionOptions:
    if chunk_overlap >= chunk_size:
        raise HTTPException(
            status_code=422,
            detail="chunk_overlap must be smaller than chunk_size",
        )

    return IngestionOptions(
        header_depth=header_depth,
        dynamic_header_depth=dynamic_header_depth,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunker=chunker,
    )


IngestionOptionsDep = Annotated[IngestionOptions, Depends(get_ingestion_options)]
