from app.models.users import User
from app.services import auth
from app.core.security import oauth2_scheme
from app.db.db import get_session
from typing import Annotated, TypeAlias
from fastapi import Depends, HTTPException, Query
from functools import lru_cache
from collections.abc import Callable, Awaitable

from app.models.user_roles import Role, UserRoleLink
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.core.config import Settings

# TODO: God file -> refactor into smaller dependency files

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
CurrentUserDep: TypeAlias = Annotated[User, Depends(get_current_user)]


async def user_has_role(user: User, role_name: str, session: SessionDep) -> bool:
    result = await session.exec(
        select(Role)
        .join(UserRoleLink, Role.id == UserRoleLink.role_id)
        .where(
            UserRoleLink.user_id == user.id,
            Role.name == role_name,
        )
    )
    return result.first() is not None


def require_role(role_name: str) -> Callable[..., Awaitable[User]]:
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
        if not await user_has_role(current_user, role_name, session):
            raise HTTPException(
                status_code=403,
                detail=f"{role_name.capitalize()} role required",
            )

        return current_user

    return dependency


def require_any_role(role_names: set[str]) -> Callable[..., Awaitable[User]]:
    async def dependency(current_user: CurrentUserDep, session: SessionDep) -> User:
        for role_name in role_names:
            if await user_has_role(current_user, role_name, session):
                return current_user

        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return dependency


TeacherDep: TypeAlias = Annotated[User, Depends(require_role("teacher"))]
AdminDep: TypeAlias = Annotated[User, Depends(require_role("admin"))]
StudentDep: TypeAlias = Annotated[User, Depends(require_role("student"))]
TeacherOrAdminDep: TypeAlias = Annotated[User, Depends(require_any_role({"teacher", "admin"}))]

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

# ------------------- USER-RELATED DEPENDENCIES ------------------- #
from app.repositories import users_repo


async def get_user_or_404(
    user_id: int,
    session: SessionDep,
) -> User:
    user = await users_repo.get_user_by_id(user_id, session)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


UserDep: TypeAlias = Annotated[User, Depends(get_user_or_404)]
UserAdminDep: TypeAlias = AdminDep


def get_admin_user(admin: AdminDep) -> User:
    return admin


AdminUserDep: TypeAlias = Annotated[User, Depends(get_admin_user)]


async def get_readable_user(
    user: UserDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> User:
    if user.id == current_user.id:
        return user

    if await user_has_role(current_user, "admin", session):
        return user

    if (
        await user_has_role(current_user, "teacher", session)
        and user.id is not None
        and await users_repo.user_has_role_by_id(user.id, "student", session)
    ):
        return user

    raise HTTPException(status_code=403, detail="User self, student viewer teacher, or admin required")


ReadableUserDep: TypeAlias = Annotated[User, Depends(get_readable_user)]

# -------------------------------------------------------------------- #

# ---------- RAG PROFILE-RELATED DEPENDENCIES ---------- #
from app.models.rag_profiles import RagProfile
from app.repositories import rag_profiles_repo


async def get_rag_profile_or_404(
    profile_id: int,
    session: SessionDep,
) -> RagProfile:
    profile = await rag_profiles_repo.get_rag_profile_by_id(profile_id, session)
    if profile is None:
        raise HTTPException(status_code=404, detail="RAG profile not found")
    return profile


RagProfileDep: TypeAlias = Annotated[
    RagProfile,
    Depends(get_rag_profile_or_404),
]
RagProfileAdminDep: TypeAlias = AdminDep


def get_readable_rag_profile(
    profile: RagProfileDep,
    _current_user: CurrentUserDep,
) -> RagProfile:
    return profile


ReadableRagProfileDep: TypeAlias = Annotated[
    RagProfile,
    Depends(get_readable_rag_profile),
]


def get_admin_rag_profile(
    profile: RagProfileDep,
    _admin: AdminDep,
) -> RagProfile:
    return profile


AdminRagProfileDep: TypeAlias = Annotated[
    RagProfile,
    Depends(get_admin_rag_profile),
]

# -------------------------------------------------------------------- #

# ---------- KNOWLEDGE GRAPH-RELATED DEPENDENCIES ---------- #
from app.models.knowledge_graph_indices import KnowledgeGraphIndex
from app.repositories import knowledge_graph_indices_repo


async def get_knowledge_graph_index_or_404(
    graph_id: int,
    session: SessionDep,
) -> KnowledgeGraphIndex:
    graph = await knowledge_graph_indices_repo.get_knowledge_graph_index_by_id(
        graph_id,
        session,
    )
    if graph is None:
        raise HTTPException(status_code=404, detail="Knowledge graph not found")
    return graph


KnowledgeGraphIndexDep: TypeAlias = Annotated[
    KnowledgeGraphIndex,
    Depends(get_knowledge_graph_index_or_404),
]


def get_admin_knowledge_graph_index(
    graph: KnowledgeGraphIndexDep,
    _admin: AdminDep,
) -> KnowledgeGraphIndex:
    return graph


AdminKnowledgeGraphIndexDep: TypeAlias = Annotated[
    KnowledgeGraphIndex,
    Depends(get_admin_knowledge_graph_index),
]

# -------------------------------------------------------------------- #

# ---------- CHUNKING PROFILE-RELATED DEPENDENCIES ---------- #
from app.models.chunking_profiles import ChunkingProfile
from app.repositories import chunking_profiles_repo


async def get_chunking_profile_or_404(
    profile_id: int,
    session: SessionDep,
) -> ChunkingProfile:
    """
    Get a chunking profile by ID
    Args:
        profile_id (int): The ID of the chunking profile to retrieve.
        session (AsyncSession): The database session for querying the 
            chunking profile.
    Returns:
        ChunkingProfile: The retrieved chunking profile object.
    Raises:
        HTTPException: If the chunking profile is not found.
    """
    profile = await chunking_profiles_repo.get_chunking_profile_by_id(profile_id, session)
    if profile is None:
        raise HTTPException(status_code=404, detail="Chunking profile not found")
    return profile


ChunkingProfileDep: TypeAlias = Annotated[
    ChunkingProfile,
    Depends(get_chunking_profile_or_404),
]
ChunkingProfileAdminDep: TypeAlias = AdminDep


def get_admin_chunking_profile(
    profile: ChunkingProfileDep,
    _admin: AdminDep,
) -> ChunkingProfile:
    """
    Get an admin chunking profile.
    Args:
        profile: The chunking profile dependency.
        _admin: The admin dependency.
    Returns:
        ChunkingProfile: The admin chunking profile.
    """
    return profile


AdminChunkingProfileDep: TypeAlias = Annotated[
    ChunkingProfile,
    Depends(get_admin_chunking_profile),
]

# -------------------------------------------------------------------- #

# ---------- DOCUMENT CHUNK-RELATED DEPENDENCIES ---------- #
from app.models.document_chunks import DocumentChunk
from app.repositories import document_chunks_repo


async def get_document_chunk_or_404(
    chunk_id: int,
    session: SessionDep,
) -> DocumentChunk:
    """
    Get document chunk by ID or raise a 404 error if not found.
    Args:
        chunk_id (int): The ID of the document chunk to retrieve.
        session (AsyncSession): The database session for querying the 
        document chunk.
    Returns:
        DocumentChunk: The retrieved document chunk object.
    Raises:
        HTTPException: If the document chunk is not found.
    """
    chunk = await document_chunks_repo.get_document_chunk_by_id(chunk_id, session)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Document chunk not found")
    return chunk


DocumentChunkDep: TypeAlias = Annotated[
    DocumentChunk,
    Depends(get_document_chunk_or_404),
]
DocumentChunkAdminDep: TypeAlias = AdminDep


def get_admin_document_chunk(
    chunk: DocumentChunkDep,
    _admin: AdminDep,
) -> DocumentChunk:
    """
    Get an admin document chunk.
    Args:
        chunk: The document chunk dependency.
        _admin: The admin dependency.
    Returns:
        DocumentChunk: The admin document chunk.
    """
    return chunk


AdminDocumentChunkDep: TypeAlias = Annotated[
    DocumentChunk,
    Depends(get_admin_document_chunk),
]

# -------------------------------------------------------------------- #

# ------------ CORPUS INDEX-RELATED DEPENDENCIES ------------ #
from app.models.corpus_indices import CorpusIndex
from app.repositories import corpus_indices_repo


async def get_corpus_index_or_404(
    index_id: int,
    session: SessionDep,
) -> CorpusIndex:
    """
    Get a corpus index by ID or raise a 404 error if not found.
    Args:
        index_id (int): The ID of the corpus index to retrieve.
        session (AsyncSession): The database session for querying the 
            corpus index.
    Returns:
        CorpusIndex: The retrieved corpus index object.
    Raises:
        HTTPException: If the corpus index is not found.
    """
    index = await corpus_indices_repo.get_corpus_index_by_id(index_id, session)
    if index is None:
        raise HTTPException(status_code=404, detail="Corpus index not found")
    return index


CorpusIndexDep: TypeAlias = Annotated[
    CorpusIndex,
    Depends(get_corpus_index_or_404),
]
CorpusIndexAdminDep: TypeAlias = AdminDep


def get_admin_corpus_index(
    index: CorpusIndexDep,
    _admin: AdminDep,
) -> CorpusIndex:
    """
    Get an admin corpus index.
    Args:
        index: The corpus index dependency.
        _admin: The admin dependency.
    Returns:
        CorpusIndex: The admin corpus index.
    """
    return index


AdminCorpusIndexDep: TypeAlias = Annotated[
    CorpusIndex,
    Depends(get_admin_corpus_index),
]

# -------------------------------------------------------------------- #

# ------------ INDEXED CHUNK-RELATED DEPENDENCIES ------------ #
from app.models.indexed_chunks import IndexedChunk
from app.repositories import indexed_chunks_repo


async def get_indexed_chunk_or_404(
    corpus_index_id: int,
    document_chunk_id: int,
    session: SessionDep,
) -> IndexedChunk:
    """
    Get an indexed chunk by corpus index ID and document chunk ID or raise 
    a 404 error if not found.
    Args:
        corpus_index_id (int): The ID of the corpus index.
        document_chunk_id (int): The ID of the document chunk.
        session (AsyncSession): The database session for querying the 
            indexed chunk.
    Returns:
        IndexedChunk: The retrieved indexed chunk object.
    Raises:
        HTTPException: If the indexed chunk is not found.
    """
    indexed_chunk = await indexed_chunks_repo.get_indexed_chunk(
        corpus_index_id,
        document_chunk_id,
        session,
    )
    if indexed_chunk is None:
        raise HTTPException(status_code=404, detail="Indexed chunk not found")
    return indexed_chunk


IndexedChunkDep: TypeAlias = Annotated[
    IndexedChunk,
    Depends(get_indexed_chunk_or_404),
]
IndexedChunkAdminDep: TypeAlias = AdminDep


def get_admin_indexed_chunk(
    indexed_chunk: IndexedChunkDep,
    _admin: AdminDep,
) -> IndexedChunk:
    """
    Get an admin indexed chunk.
    Args:
        indexed_chunk: The indexed chunk dependency.
        _admin: The admin dependency.
    Returns:
        IndexedChunk: The admin indexed chunk.
    """
    return indexed_chunk


AdminIndexedChunkDep: TypeAlias = Annotated[
    IndexedChunk,
    Depends(get_admin_indexed_chunk),
]

# -------------------------------------------------------------------- #

# --------------- CORPUS-RELATED DEPENDENCIES --------------- #
from app.models.corpus import Corpus
from app.repositories import corpus_repo

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
    corpus = await corpus_repo.get_corpus_by_id(corpus_id, session)
    if corpus is None:
        raise HTTPException(status_code=404, detail="Corpus not found")
    return corpus


CorpusDep: TypeAlias = Annotated[Corpus, Depends(get_corpus_or_404)]
CorpusCreatorDep: TypeAlias = TeacherOrAdminDep
CorpusViewerDep: TypeAlias = TeacherOrAdminDep

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


OwnedCorpusDep: TypeAlias = Annotated[Corpus, Depends(get_owned_corpus)]


async def get_writable_corpus(
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
    if await user_has_role(current_user, "admin", session):
        return corpus

    if (
        await user_has_role(current_user, "teacher", session)
        and corpus.created_by_user_id == current_user.id
    ):
        return corpus

    raise HTTPException(status_code=403, detail="Corpus creator teacher or admin required")


WritableCorpusDep: TypeAlias = Annotated[Corpus, Depends(get_writable_corpus)]


async def get_student_accessible_corpus(
    corpus: CorpusDep,
    student: StudentDep,
    session: SessionDep,
) -> Corpus:
    """
    Dependency to ensure that the current user (student) has access to 
    the corpus.
    Args:
        corpus (Corpus): The corpus being accessed.
        student (User): The currently authenticated student.
        session (AsyncSession): The database session for querying access 
            permissions.
    Returns:
        Corpus: The corpus if the student has access.
    Raises:
        HTTPException: If the student does not have access to the corpus.
    """
    if corpus.id is None:
        raise HTTPException(status_code=404, detail="Corpus not found")

    if await corpus_repo.user_has_simulation_access_to_corpus(corpus.id, student.id, session):
        return corpus

    raise HTTPException(status_code=403, detail="Student does not have access to this corpus")


StudentAccessibleCorpusDep: TypeAlias = Annotated[
    Corpus,
    Depends(get_student_accessible_corpus),
]
# -------------------------------------------------------------------- #

# ------------ RAW DOCUMENT-RELATED DEPENDENCIES ------------ #
from app.models.raw_documents import RawDocument
from app.repositories import raw_documents_repo


async def get_raw_document_or_404(
    raw_document_id: int,
    session: SessionDep,
) -> RawDocument:
    """
    Get a raw document by ID or raise a 404 error if not found.
    Args:
        raw_document_id (int): The ID of the raw document to retrieve.
        session (AsyncSession): The database session for querying the 
            raw document.
    Returns:
        RawDocument: The retrieved raw document object.
    Raises:
        HTTPException: If the raw document is not found.    
    """
    raw_document = await raw_documents_repo.get_raw_document_by_id(raw_document_id, session)
    if raw_document is None:
        raise HTTPException(status_code=404, detail="Raw document not found")
    return raw_document


RawDocumentDep: TypeAlias = Annotated[RawDocument, Depends(get_raw_document_or_404)]
RawDocumentCreatorDep: TypeAlias = TeacherOrAdminDep
RawDocumentViewerDep: TypeAlias = Annotated[
    User,
    Depends(require_any_role({"admin", "teacher", "student"})),
]


async def get_writable_raw_document(
    raw_document: RawDocumentDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> RawDocument:
    """
    Dependency to ensure that the current user is either the owner of the 
    raw document or has an admin role.
    Args:
        raw_document (RawDocument): The raw document being accessed.
        current_user (User): The currently authenticated user.
        session (AsyncSession): The database session for querying user roles.
    Returns:
        RawDocument: The raw document if the user is the owner or an admin.
    Raises:
        HTTPException: If the user is neither the owner nor an admin.
    """
    if await user_has_role(current_user, "admin", session):
        return raw_document

    if (
        await user_has_role(current_user, "teacher", session)
        and raw_document.uploaded_by_user_id == current_user.id
    ):
        return raw_document

    raise HTTPException(status_code=403, detail="Raw document owner teacher or admin required")


WritableRawDocumentDep: TypeAlias = Annotated[
    RawDocument,
    Depends(get_writable_raw_document),
]

# -------------------------------------------------------------------- #

# ---------- COUNTERPART PERSONA-RELATED DEPENDENCIES ---------- #
from app.models.counterpart_personas import CounterPartPersonas
from app.repositories import counterpart_personas_repo


async def get_counterpart_persona_or_404(
    persona_id: int,
    session: SessionDep,
) -> CounterPartPersonas:
    """
    Get a counterpart persona by ID or raise a 404 error if not found.
    Args:
        persona_id (int): The ID of the counterpart persona to retrieve.
        session (AsyncSession): The database session for querying the 
            counterpart persona.
    Returns:
        CounterPartPersonas: The retrieved counterpart persona object.
    Raises:
        HTTPException: If the counterpart persona is not found.
    """
    persona = await counterpart_personas_repo.get_counterpart_persona_by_id(persona_id, session)
    if persona is None:
        raise HTTPException(status_code=404, detail="Counterpart persona not found")
    return persona


CounterpartPersonaDep: TypeAlias = Annotated[
    CounterPartPersonas,
    Depends(get_counterpart_persona_or_404),
]
CounterpartPersonaCreatorDep: TypeAlias = TeacherOrAdminDep


def get_visible_counterpart_persona(
    persona: CounterpartPersonaDep,
    _current_user: CurrentUserDep,
) -> CounterPartPersonas:
    """
    Get a counterpart persona if it is visible to the current user.
    Args:
        persona (CounterPartPersonas): The counterpart persona being accessed.
            _current_user (User): The currently authenticated user.
    Returns:
        CounterPartPersonas: The counterpart persona if it is visible to the user.
    """
    return persona


CounterpartPersonaViewerDep: TypeAlias = Annotated[
    CounterPartPersonas,
    Depends(get_visible_counterpart_persona),
]


async def get_writable_counterpart_persona(
    persona: CounterpartPersonaDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> CounterPartPersonas:
    """
    Dependency to ensure that the current user is either the creator of the
    counterpart persona or has an admin role.
    Args:
        persona (CounterPartPersonas): The counterpart persona being accessed.
        current_user (User): The currently authenticated user.
        session (AsyncSession): The database session for querying user roles.
    Returns:
        CounterPartPersonas: The counterpart persona if the user is the 
        creator or an admin.
    Raises:
        HTTPException: If the user is neither the creator nor an admin.
    """
    if await user_has_role(current_user, "admin", session):
        return persona

    if (
        await user_has_role(current_user, "teacher", session)
        and persona.created_by_user_id == current_user.id
    ):
        return persona

    raise HTTPException(status_code=403, detail="Counterpart persona creator teacher or admin required")


WritableCounterpartPersonaDep: TypeAlias = Annotated[
    CounterPartPersonas,
    Depends(get_writable_counterpart_persona),
]


async def get_copyable_counterpart_persona(
    persona: CounterpartPersonaDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> CounterPartPersonas:
    """
    Dependency to ensure that the current user has the role of teacher or admin
    to copy a counterpart persona.
    Args:
        persona (CounterPartPersonas): The counterpart persona being accessed.
        current_user (User): The currently authenticated user.
        session (AsyncSession): The database session for querying user roles.
    Returns:
        CounterPartPersonas: The counterpart persona if the user has the 
        required role.
    Raises:
        HTTPException: If the user does not have the required role.
    """
    if await user_has_role(current_user, "admin", session):
        return persona

    if await user_has_role(current_user, "teacher", session):
        return persona

    raise HTTPException(status_code=403, detail="Teacher or admin role required")


CopyableCounterpartPersonaDep: TypeAlias = Annotated[
    CounterPartPersonas,
    Depends(get_copyable_counterpart_persona),
]

# -------------------------------------------------------------------- #

# ------------------- SESSION-RELATED DEPENDENCIES ------------------- #
from app.models.sessions import Session as UserSession
from app.repositories import sessions_repo


async def get_session_or_404(
    session_id: int,
    session: SessionDep,
) -> UserSession:
    """
    Dependency to retrieve a UserSession by ID or raise a 404 error if 
    not found.
    Args:
        session_id (int): The ID of the UserSession to retrieve.
        session (AsyncSession): The database session for querying the 
            UserSession.
    Returns:
        UserSession: The retrieved UserSession object.
    Raises:
        HTTPException: If the UserSession is not found.
    """
    user_session = await sessions_repo.get_session_by_id(session_id, session)
    if user_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return user_session


UserSessionDep: TypeAlias = Annotated[UserSession, Depends(get_session_or_404)]


def get_admin_session(
    user_session: UserSessionDep,
    _admin: AdminDep,
) -> UserSession:
    """
    Dependency to retrieve an admin UserSession.
    Args:
        user_session (UserSession): The UserSession object.
        _admin (User): The currently authenticated admin user.
    Returns:
        UserSession: The admin UserSession object.
    """
    return user_session


AdminSessionDep: TypeAlias = Annotated[UserSession, Depends(get_admin_session)]

# -------------------------------------------------------------------- #

# ------------------ SCENARIO-RELATED DEPENDENCIES ------------------ #
from app.models.scenarios import Scenario
from app.repositories import scenarios_repo


async def get_scenario_or_404(
    scenario_id: int,
    session: SessionDep,
) -> Scenario:
    """
    Dependency to retrieve a Scenario by ID or raise a 404 error if not found.
    Args:
        scenario_id (int): The ID of the Scenario to retrieve.
        session (AsyncSession): The database session for querying the Scenario.
    Returns:
        Scenario: The retrieved Scenario object.
    Raises:
        HTTPException: If the Scenario is not found.
    """
    scenario = await scenarios_repo.get_scenario_by_id(scenario_id, session)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


ScenarioDep: TypeAlias = Annotated[Scenario, Depends(get_scenario_or_404)]
ScenarioCreatorDep: TypeAlias = TeacherOrAdminDep


def get_visible_scenario(
    scenario: ScenarioDep,
    _current_user: CurrentUserDep,
) -> Scenario:
    """
    Dependency to retrieve a visible Scenario.
    Args:
        scenario (Scenario): The Scenario object.
        _current_user (User): The currently authenticated user.
    Returns:
        Scenario: The visible Scenario object.
    """
    return scenario


ScenarioViewerDep: TypeAlias = Annotated[Scenario, Depends(get_visible_scenario)]


async def get_writable_scenario(
    scenario: ScenarioDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Scenario:
    """
    Dependency to retrieve a writable Scenario.
    Args:
        scenario (Scenario): The Scenario object.
        current_user (User): The currently authenticated user.
        session (AsyncSession): The database session for querying user roles.
    Returns:
        Scenario: The writable Scenario object.
    Raises:
        HTTPException: If the user does not have permission to write to 
        the Scenario.
    """
    if await user_has_role(current_user, "admin", session):
        return scenario

    if (
        await user_has_role(current_user, "teacher", session)
        and scenario.created_by_user_id == current_user.id
    ):
        return scenario

    raise HTTPException(status_code=403, detail="Scenario creator teacher or admin required")


WritableScenarioDep: TypeAlias = Annotated[
    Scenario,
    Depends(get_writable_scenario),
]

# -------------------------------------------------------------------- #

# ------------------ SIMULATION-RELATED DEPENDENCIES ----------------- #
from app.models.simulations import Simulation
from app.repositories import simulations_repo


TERMINAL_SIMULATION_STATUSES = {"completed", "cancelled", "failed"}


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
    simulation = await simulations_repo.get_simulation_by_id(simulation_id, session)
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


async def get_completed_accessible_simulation(
    simulation: SimulationDep,
    current_user: TeacherOrAdminDep,
) -> Simulation:
    """
    Dependency to retrieve a completed accessible Simulation.
    Args:
        simulation (Simulation): The Simulation object.
        current_user (User): The currently authenticated user.
    Returns:
        Simulation: The completed accessible Simulation object.
    Raises:
        HTTPException: If the simulation is not completed.
    """
    if simulation.status != "completed":
        raise HTTPException(status_code=403, detail="Completed simulation access required")
    return simulation


CompletedAccessibleSimulationDep = Annotated[
    Simulation,
    Depends(get_completed_accessible_simulation),
]


async def get_readable_simulation(
    simulation: SimulationDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Simulation:
    """
    Dependency to retrieve a readable Simulation.
    Args:
        simulation (Simulation): The Simulation object.
        current_user (User): The currently authenticated user.
        session (AsyncSession): The database session for querying user roles.
    Returns:
        Simulation: The readable Simulation object.
    Raises:
        HTTPException: If the user does not have access to the simulation.
    """
    if simulation.status == "completed":
        if await user_has_role(current_user, "teacher", session) or await user_has_role(current_user, "admin", session):
            return simulation
    return await get_accessible_simulation(simulation, current_user, session)


ReadableSimulationDep = Annotated[
    Simulation,
    Depends(get_readable_simulation),
]


def get_teacher_review_simulation(
    simulation: SimulationDep,
    _reviewer: TeacherOrAdminDep,
) -> Simulation:
    """
    Dependency to retrieve a Simulation for teacher review.
    Args:
        simulation (Simulation): The Simulation object.
        _reviewer (User): The currently authenticated teacher or admin.
    Returns:
        Simulation: The Simulation object for review.
    Raises:
        HTTPException: If the simulation is not completed.
    """
    if simulation.status != "completed":
        raise HTTPException(status_code=409, detail="Only completed simulations can be reviewed")
    return simulation


TeacherReviewSimulationDep: TypeAlias = Annotated[
    Simulation,
    Depends(get_teacher_review_simulation),
]


def get_student_mutable_simulation(
    simulation: SimulationDep,
    student: StudentDep,
) -> Simulation:
    """
    Dependency to retrieve a mutable Simulation for a student.
    Args:
        simulation (Simulation): The Simulation object.
        student (User): The currently authenticated student.
    Returns:
        Simulation: The mutable Simulation object.
    Raises:
        HTTPException: If the student does not have permission to modify the Simulation.
    """
    if student.id not in {simulation.user_id_owner, simulation.user_id_participant}:
        raise HTTPException(status_code=403, detail="Simulation owner or participant required")

    if simulation.status in TERMINAL_SIMULATION_STATUSES:
        raise HTTPException(status_code=409, detail="Ended simulations cannot be modified")

    return simulation


StudentMutableSimulationDep: TypeAlias = Annotated[
    Simulation,
    Depends(get_student_mutable_simulation),
]

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

from app.models.prompts import Prompt
from app.repositories import prompts_repo


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
    prompt = await prompts_repo.get_prompt_by_id(prompt_id, session)
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt


PromptDep: TypeAlias = Annotated[Prompt, Depends(get_prompt_or_404)]
PromptCreatorDep: TypeAlias = TeacherOrAdminDep
PromptAdminDep: TypeAlias = AdminDep


def get_admin_prompt(
    prompt: PromptDep,
    _admin: AdminDep,
) -> Prompt:
    return prompt


AdminPromptDep: TypeAlias = Annotated[Prompt, Depends(get_admin_prompt)]


async def get_readable_prompt(
    prompt: PromptDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Prompt:
    """
    Dependency to ensure that the current user can read the prompt.
    Args:
        prompt (Prompt): The prompt being accessed.
        current_user (User): The currently authenticated user.
        session (AsyncSession): The database session for querying user 
            roles.
    Returns:
        Prompt: The prompt if the user can read it.
    Raises:
        HTTPException: If the user cannot read the prompt.
    """
    if await user_has_role(current_user, "admin", session):
        return prompt

    if prompt.is_system:
        raise HTTPException(status_code=403, detail="System prompt admin access required")

    if prompt.owner_id == current_user.id:
        return prompt

    raise HTTPException(status_code=403, detail="Prompt owner or admin required")


ReadablePromptDep: TypeAlias = Annotated[Prompt, Depends(get_readable_prompt)]


async def get_editable_prompt(
    prompt: PromptDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Prompt:
    """
    Dependency to ensure that the current user can edit the prompt.
    Args:
        prompt (Prompt): The prompt being accessed.
        current_user (User): The currently authenticated user.
    Returns:
        Prompt: The prompt if the user can edit it.
    Raises:
        HTTPException: If the user cannot edit the prompt.
    """
    if await user_has_role(current_user, "admin", session):
        return prompt

    if prompt.is_system:
        raise HTTPException(status_code=403, detail="System prompts cannot be edited here")

    if (
        await user_has_role(current_user, "teacher", session)
        and prompt.owner_id == current_user.id
    ):
        return prompt

    raise HTTPException(status_code=403, detail="Prompt owner teacher or admin required")


EditablePromptDep: TypeAlias = Annotated[Prompt, Depends(get_editable_prompt)]


async def get_deletable_prompt(
    prompt: PromptDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Prompt:
    """
    Dependency to ensure that the current user can delete the prompt.
    Args:
        prompt (Prompt): The prompt being accessed.
        current_user (User): The currently authenticated user.
        session (AsyncSession): The database session for querying user roles.
    Returns:
        Prompt: The prompt if the user can delete it.
    Raises:
        HTTPException: If the user cannot delete the prompt.
    """
    if await user_has_role(current_user, "admin", session):
        return prompt

    if prompt.is_system:
        raise HTTPException(status_code=403, detail="System prompt admin access required")

    if (
        await user_has_role(current_user, "teacher", session)
        and prompt.owner_id == current_user.id
    ):
        return prompt

    raise HTTPException(status_code=403, detail="Prompt owner teacher or admin required")


DeletablePromptDep: TypeAlias = Annotated[Prompt, Depends(get_deletable_prompt)]


async def get_copyable_prompt(
    prompt: PromptDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Prompt:
    """
    Dependency to ensure that the current user can copy the prompt.
    Args:
        prompt (Prompt): The prompt being accessed.
        current_user (User): The currently authenticated user.
        session (AsyncSession): The database session for querying user roles.
    Returns:
        Prompt: The prompt if the user can copy it.
    Raises:
        HTTPException: If the user cannot copy the prompt.
    """
    if await user_has_role(current_user, "admin", session):
        return prompt

    if prompt.is_system:
        raise HTTPException(status_code=403, detail="System prompt admin access required")

    if prompt.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Prompt owner or admin required")

    return prompt


CopyablePromptDep: TypeAlias = Annotated[Prompt, Depends(get_copyable_prompt)]

### ------------------- RAG-RELATED DEPENDENCIES ------------------- ###
# Embeddings

from langchain_core.embeddings import Embeddings
from app.airag.embeddings.embeddings import choose_embedding_model


def get_embedding_model(
    model_name: str = "mini-l6-v2",
) -> Embeddings:
    """
    Dependency to get the embedding model.
    Args:
        model_name (str): The name of the embedding model.
    Returns:
        Embeddings: The embedding model instance.
    """
    embedding_model, _ = choose_embedding_model(model_name)
    return embedding_model

EmbeddingModelDep = Annotated[Embeddings, Depends(get_embedding_model)]

# Metadata

def get_embedding_config(model_name: str = "mini-l6-v2") -> dict[str, int | str]:
    """
    Dependency to get the embedding configuration.
    Args:
        model_name (str): The name of the embedding model.
    Returns:
        dict[str, int | str]: The embedding configuration.
    """
    _, metadata = choose_embedding_model(model_name)
    return {
        "model_name": model_name,
        "dimensionality": metadata["dimensionality"],
    }


EmbeddingConfigDep = Annotated[dict[str, int | str], Depends(get_embedding_config)]

# LLM
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from app.airag.llm_models.llm_models import get_llm


def get_chat_model(
    provider: str = "openai",
    model_name: str = "gpt-4o-mini",
    temperature: float = 0.0,
) -> ChatOpenAI | ChatOllama:
    """
    Dependency to get the chat model.
    Args:
        provider (str): The name of the LLM provider.
        model_name (str): The name of the LLM model.
        temperature (float): The temperature for the LLM.
    Returns:
        ChatOpenAI | ChatOllama: The chat model instance.
    Raises:
        HTTPException: If the LLM provider is unavailable.
    """
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
from app.models.vector_stores import VectorStore
from app.repositories import vector_stores_repo

async def get_vector_store_record_or_404(
    vector_store_id: int,
    session: SessionDep,
) -> VectorStore:
    """
    Dependency to get a vector store record by ID or raise a 404 error.
    Args:
        vector_store_id (int): The ID of the vector store.
        session (AsyncSession): The database session for querying vector 
            stores.
    Returns:
        VectorStore: The vector store record.
    Raises:
        HTTPException: If the vector store is not found.
    """
    vector_store = await vector_stores_repo.get_vector_store_by_id(vector_store_id, session)

    if vector_store is None:
        raise HTTPException(status_code=404, detail="Vector store not found")

    return vector_store


VectorStoreRecordDep = Annotated[
    VectorStore,
    Depends(get_vector_store_record_or_404),
]


def get_admin_vector_store(
    vector_store: VectorStoreRecordDep,
    _admin: AdminDep,
) -> VectorStore:
    """
    Dependency to get the admin vector store.
    Args:
        vector_store (VectorStore): The vector store record.
        _admin (AdminDep): The admin dependency.
    Returns:
        VectorStore: The admin vector store.
    """
    return vector_store


AdminVectorStoreDep: TypeAlias = Annotated[
    VectorStore,
    Depends(get_admin_vector_store),
]
VectorStoreAdminDep: TypeAlias = AdminDep

from app.airag.vector_stores.vector_stores import (
    instantiate_chroma_vector_store,
    load_faiss_vector_store,
)


async def get_runtime_vector_store(
    vector_store_record: VectorStoreRecordDep,
    embedding_model: EmbeddingModelDep,
):
    """
    Dependency to get the runtime vector store based on the vector store 
    record and embedding model.
    Args:
        vector_store_record (VectorStoreRecordDep): The vector store record.
        embedding_model (EmbeddingModelDep): The embedding model.
    Returns:
        object: The runtime vector store instance.
    Raises:
        HTTPException: If the vector store backend is unsupported.
    """
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

# Reranker
from sentence_transformers import CrossEncoder

@lru_cache
def get_cross_encoder() -> CrossEncoder:
    """
    Dependency to get the cross encoder model.
    Returns:
        CrossEncoder: The cross encoder model instance.
    """
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
    """
    Dependency to get the retrieval options.
    Args:
        k (int): The number of top results to retrieve.
        rerank (bool): Whether to rerank the retrieved results.
        rerank_top_k (int): The number of top results to rerank.
    Returns:
        RetrievalOptions: The retrieval options instance.
    """
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
    """
    Dependency to get the ingestion options.
    Args:
        header_depth (int): The header depth for ingestion.
        dynamic_header_depth (bool): Whether to use dynamic header depth.
        chunk_size (int): The size of each chunk.
        chunk_overlap (int): The overlap between chunks.
        chunker (str): The chunking method.
    Returns:
        IngestionOptions: The ingestion options instance.
    """
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

# Ingestion options alias for dependency injection
IngestionOptionsDep = Annotated[IngestionOptions, Depends(get_ingestion_options)]


class IngestionExecutionOptions(BaseModel):
    header_depth: int = 2
    dynamic_header_depth: bool = False


def get_ingestion_execution_options(
    header_depth: int = Query(default=2, ge=1, le=6),
    dynamic_header_depth: bool = Query(default=False),
) -> IngestionExecutionOptions:
    """
    Get ingestion execution options.
    Args:
        header_depth (int): The header depth for ingestion execution.
        dynamic_header_depth (bool): Whether to use dynamic header depth for 
            ingestion execution.
    Returns:
        IngestionExecutionOptions: The ingestion execution options instance.
    """
    return IngestionExecutionOptions(
        header_depth=header_depth,
        dynamic_header_depth=dynamic_header_depth,
    )


IngestionExecutionOptionsDep = Annotated[IngestionExecutionOptions, Depends(get_ingestion_execution_options)]

# Chunking Options
from app.schemas.chunking_schemas import ChunkingOptions


def get_chunking_options(
    chunker: str = Query(default="recursive"),
    chunk_size: int = Query(default=1000, ge=100, le=8000),
    chunk_overlap: int = Query(default=200, ge=0, le=2000),
    preview: bool = Query(default=False),
    breakpoint_threshold_type: str = Query(default="percentile"),
    breakpoint_threshold_amount: int = Query(default=90, ge=1),
    buffer_size: int = Query(default=1, ge=0),
) -> ChunkingOptions:
    """
    Dependency to get the chunking options.
    Args:
        chunker (str): The chunking method.
        chunk_size (int): The size of each chunk.
        chunk_overlap (int): The overlap between chunks.
        preview (bool): Whether to enable preview mode.
        breakpoint_threshold_type (str): The type of breakpoint threshold.
        breakpoint_threshold_amount (int): The amount for the breakpoint 
            threshold.
        buffer_size (int): The buffer size.
    Returns:
        ChunkingOptions: The chunking options instance.
    """
    if chunk_overlap >= chunk_size:
        raise HTTPException(
            status_code=422,
            detail="chunk_overlap must be smaller than chunk_size",
        )

    if chunker not in {"recursive", "semantic", "hybrid"}:
        raise HTTPException(
            status_code=422,
            detail="chunker must be one of: recursive, semantic, hybrid",
        )

    return ChunkingOptions(
        chunker=chunker,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        preview=preview,
        breakpoint_threshold_type=breakpoint_threshold_type,
        breakpoint_threshold_amount=breakpoint_threshold_amount,
        buffer_size=buffer_size,
    )


ChunkingOptionsDep = Annotated[ChunkingOptions, Depends(get_chunking_options)]


class ChunkingExecutionOptions(BaseModel):
    preview: bool = False


def get_chunking_execution_options(
    preview: bool = Query(default=False),
) -> ChunkingExecutionOptions:
    """
    Dependency to get the chunking execution options.
    Args:
        preview (bool): Whether to enable preview mode.
    Returns:
        ChunkingExecutionOptions: The chunking execution options instance.
    """
    return ChunkingExecutionOptions(preview=preview)


ChunkingExecutionOptionsDep = Annotated[ChunkingExecutionOptions, Depends(get_chunking_execution_options)]
