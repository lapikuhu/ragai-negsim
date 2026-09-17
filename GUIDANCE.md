# Project Guidance

This summarizes the repository's domain, architecture, and recurring patterns. Feature specifications, migrations, and current implementation and test behavior take precedence when they disagree with this guide.

## Purpose and Domain

OpenWiki is an educational negotiation simulator. Learners negotiate with AI counterparts, receive coaching and evaluation, and use uploaded course or domain documents for grounded assistance.

The backend is the primary system under active development. Major domains include authentication, document ingestion, retrieval infrastructure, simulations, learner assistance, and persistent RAG evaluation.

## Core Concepts

- **Simulation:** Combines a scenario, counterpart persona, prompts, learner settings, retrieval configuration, coaching, and evaluation.
- **Scenario context:** Public and side-private information are deliberately separated. Public API schemas must not expose private context.
- **Corpus pipeline:** PDFs are associated with corpora, parsed, chunked, grouped into named `CorpusChunkSet` snapshots, and indexed.
- **Retrieval profiles:** CRAG supports dense, BM25, and hybrid retrieval; GraphRAG uses Neo4j-backed graph retrieval.
- **Evidence ledger:** Stores filtered sources, pipeline steps, quality checks, model metadata, and token usage.
- **RAG evaluation:** Runs the production response pipeline against isolated resources and persists immutable configuration snapshots and results.

## Architecture

Backend requests generally follow:

`FastAPI route -> service -> repository -> SQLModel/PostgreSQL`

- Routes handle HTTP contracts and dependency-based authorization.
- Services perform application orchestration, attribution, and LLM or graph invocation.
- Repositories own persistence queries and transaction boundaries.
- Models define SQLModel persistence entities; schemas define request, internal, public, and authoring views.
- LangGraph workflows under `app/airag/` orchestrate negotiation and retrieval behavior.
- Durable jobs use database-backed queues with application-owned asynchronous coordinators.

The React frontend mirrors backend domains. Pages use feature-level TanStack Query hooks and generated OpenAPI types.

## Technology Stack

- Python 3.12-3.13, FastAPI, Pydantic, SQLModel, async SQLAlchemy
- PostgreSQL, Alembic, Neo4j with APOC
- LangChain, LangGraph, LangSmith, RAGAS
- Chroma, FAISS, PGVector, BM25, optional Redis embedding cache
- React 19, TypeScript strict mode, Vite, Tailwind CSS
- TanStack Query, React Router, `openapi-fetch`
- pytest/pytest-asyncio and Vitest/Testing Library
- `uv` and npm for dependency management

## Development Conventions

- Use package-qualified backend imports such as `app.services...`.
- Keep routes thin and enforce authentication, roles, and resource loading through dependencies where practical.
- Define distinct schemas when audiences have different visibility, especially public versus authoring data.
- Use timezone-aware UTC timestamps and repository transaction helpers.
- Treat `app/core/policies.py` as locked application policy and `app/core/config.py` as environment configuration.
- Use generated frontend API types and feature query hooks; invalidate stable query keys after mutations.
- Database model changes require Alembic migrations and model registration for metadata discovery.

## Architectural Preferences

- PostgreSQL is the system of record.
- Backend compatibility checks are authoritative; frontend filtering is convenience rather than enforcement.
- Persist exact artifact identities, revisions, and checksums instead of inferring relationships.
- Keep dense, BM25, and graph artifacts independently manageable.
- Reuse the canonical response pipeline across production and evaluation.
- Filter evidence and projected agent state to prevent private-context leakage.
- Long-running work should persist queue state, progress, cancellation, recovery, and cleanup status.

## Testing and Quality

Backend CI runs compilation and unit tests on Python 3.12 and 3.13, plus PostgreSQL and Neo4j integration jobs. Frontend CI runs strict type checking, production build, and Vitest.

Common checks:

```powershell
uv run python -m compileall app tests/unit
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"
uv run pytest tests/unit -p pytest_asyncio.plugin -q
uv run pytest tests/integration -m "integration and postgres" -p pytest_asyncio.plugin -q
uv run pytest tests/integration -m "integration and neo4j" -p pytest_asyncio.plugin -q

cd frontend
npm run typecheck
npm run build
npm run test
```

Match tests to the changed boundary: route, service, and repository tests for backend behavior; graph and evidence tests for retrieval changes; and page, router, and sidebar tests for frontend workflows.

## Repository Navigation

- `app/main.py`: application bootstrap and coordinator lifecycle
- `app/core/`: settings, policy, security, and dependencies
- `app/web/routes/`: HTTP endpoints
- `app/services/`: business logic and orchestration
- `app/repositories/`: persistence
- `app/models/`, `app/schemas/`: database and API contracts
- `app/airag/`: agent, retrieval, evaluation, and observability pipelines
- `frontend/src/`: React application
- `tests/`: backend unit and integration tests
- `migrations/`: Alembic revisions

## Important Exceptions or Transitional Areas

- `app/services/simulations_service.py` and `app/core/dependencies.py` are acknowledged large modules.
- Some domain invariants currently live in repositories rather than services.
- Frontend API access is transitional: generated `openapi-fetch` calls coexist with manual JSON request helpers.
- In-process coordinators assume a single Uvicorn worker; multi-process deployment requires leader election.
- Graph caches can retain loaded BM25 resources and may require explicit clearing or process restart.
- Startup seeds data but assumes Alembic migrations have already run.

## Sources of Authority

Start with `openwiki/quickstart.md`, then follow its architecture, domain, and operations links. For conflicts, prefer current tests and implementation, followed by migrations and OpenWiki. Treat plans under `plans/` and `docs/plans/` as historical or prospective unless reflected in code.