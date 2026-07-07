# Backend architecture

The backend is a FastAPI application organized around a conventional route → service → repository layering, with SQLModel models and Pydantic schemas bridging persistence and API contracts.

## Core application wiring
- `app/main.py` creates the FastAPI app, configures CORS, registers request logging middleware, and includes the route modules.
- Startup uses a lifespan handler to seed base data and mark interrupted indexing jobs as failed.
- `app/core/config.py` loads settings from `.env` and also configures LangSmith environment variables when tracing is enabled.
- `app/core/dependencies.py` centralizes session, authentication, role checks, pagination, and resource-loading dependencies.

## Layering
### Routes
Route modules live under `app/web/routes/` and expose the API surface. They are thin wrappers around service calls and dependency checks.

### Services
Service modules under `app/services/` contain application logic. This is where orchestration happens for simulations, ingestion, chunking, retrieval, sessions, and user-adjacent workflows.

### Repositories
Repository modules under `app/repositories/` isolate persistence queries and keep route/service code from reaching directly into SQLModel/SQLAlchemy query logic.

### Schemas and models
- `app/models/` contains the SQLModel ORM models.
- `app/schemas/` contains request/response shapes and domain-specific payloads.

## Access control and dependencies
The project uses FastAPI dependencies for most cross-cutting concerns:
- Authentication via JWT token resolution.
- Role checks for student, teacher, and admin access.
- Resource loaders such as `get_*_or_404` helpers.
- Pagination via a reusable `skip`/`limit` dependency.

A useful detail for future changes: permissions are usually enforced in dependencies rather than directly inside route handlers. That keeps route code simple and makes policy changes easier to test.

## Important backend entrypoints
- `app/main.py` — application bootstrap
- `app/core/config.py` — settings and tracing config
- `app/core/dependencies.py` — auth, roles, pagination, and loader helpers
- `app/db/db.py` — database session/startup behavior
- `migrations/env.py` — Alembic migration environment

## Domain route groups
The API is broad, but the most important route families are:
- users and sessions
- documents, corpora, chunking profiles, and document chunks
- RAG profiles, vector stores, and knowledge graphs
- scenarios, prompts, and counterpart personas
- simulations and learner/evaluation flows

## Recent evolution worth knowing
Recent commits show the backend changing in a few important ways:
- Learner assistant support was added to simulations and later exposed in the simulation cockpit.
- CRAG and GraphRAG both gained source capture, which is now reflected in the evidence ledger.
- Raw documents gained corpus associations, making document ingestion more clearly tied to simulation inputs.
- Simulation review and evaluation flows have become more explicit, including learner-facing debug traces.
- Security hardening also tightened JWT expiry handling and added PDF signature/size checks for raw uploads.
- Prompt handling now has a guard scaffold in `app/airag/prompt_guard/` and a guarded runnable wrapper in `app/airag/observability/llm_usage.py`.
- Simulation turns and learner questions now call the guard at the service layer before negotiation-graph or learner-agent invocation.
- CRAG retrieval now blocks injection-like queries before retrieval and logs the blocked pipeline step instead of returning documents.

These changes matter because many services now return richer metadata than the old route names suggest, and some request paths now reject unsafe payloads before the runnable, graph, or upload code ever executes. When modifying a domain, inspect the service layer and tests first; route signatures often lag behind the true business rules.

## What to watch out for
- `app/services/simulations_service.py` has grown into a large orchestration module and is explicitly marked as a candidate for splitting.
- `app/core/dependencies.py` is also a large catch-all. Be careful when adding new dependencies so the file does not become harder to navigate.
- Startup assumes migrations have already been applied.
- The app expects a PostgreSQL database and Neo4j settings even if a local flow does not use graph retrieval.

## Source pointers
- `app/main.py`
- `app/core/config.py`
- `app/core/dependencies.py`
- `app/web/routes/simulations_route.py`
- `app/services/simulations_service.py`
- `app/services/simulation_learner_service.py`
- `app/web/routes/raw_documents_route.py`
- `app/web/routes/document_chunks_route.py`
