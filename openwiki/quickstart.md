# OpenWiki quickstart

## What this repository is
This repository is a FastAPI + React application for an educational negotiation simulator. Learners practice negotiation scenarios against AI counterparts, receive coach feedback and evaluation, and work with uploaded course or domain documents that ground the simulation flow.

The backend is the main system under active development. It manages users, roles, raw document uploads, corpora, chunking and indexing, retrieval profiles, simulations, learner-assistant questions, and the LangGraph-based agent flows that drive negotiation turns.

## Start here
- [Backend architecture](architecture/backend.md)
- [Simulation and learner domain](domains/simulations.md)
- [Knowledge and retrieval domain](domains/knowledge-retrieval.md)
- [Frontend architecture](architecture/frontend.md)
- [Testing and operations](operations/testing.md)

## High-level flow
1. An admin or teacher uploads PDF source documents.
2. Documents are linked to corpora and ingested into chunks and vector stores.
3. Retrieval profiles choose CRAG or GraphRAG behavior for grounding.
4. A simulation is created with scenario, counterpart persona, prompts, and optional learner assistant settings.
5. During a turn, the negotiation graph coordinates intent classification, counterpart generation, coaching, evaluation, and evidence capture.
6. The learner can also ask the autonomous learner assistant for advice during a simulation.

## Major domains
### Authentication and access control
The app uses JWT-based auth with role-based FastAPI dependencies. Routes are split between general user access, teacher/admin access, and admin-only management.

### Documents, corpora, and retrieval
Raw PDF documents are uploaded, linked to corpora, ingested, chunked, and stored for retrieval. The system supports both corrective RAG and GraphRAG flows and records sources in an evidence ledger. Recent security changes add stricter PDF upload validation, raw-document source verification now tracks changing on-disk file state, and recent prompt work intercepts simulation turns and learner questions at the service layer before graph or agent invocation, with guard checks also enforced in the shared LLM invocation path.

### Simulations and agent orchestration
Simulations are the core product object. They combine scenario data, counterpart personas, prompts, learner settings, retrieval context, coach feedback, and evaluator output in a LangGraph-driven negotiation workflow.

### Frontend application
The React frontend mirrors backend domains with routes for simulations, documents, corpora, evaluations, knowledge graphs, indexing, and admin management.

## Repository layout
- `app/` — backend application code
- `frontend/` — React + TypeScript user interface
- `tests/` — pytest suite covering API, services, graph behavior, and domain rules
- `migrations/` — Alembic migration environment
- `scripts/` — bootstrap, seeding, and utility scripts
- `docs/` — supplementary planning/specification material

## Recommended reading order for future agents
1. Read this page.
2. Read [Backend architecture](architecture/backend.md) to understand how requests flow through routes, services, and dependencies.
3. Read [Simulation and learner domain](domains/simulations.md) before changing turn handling, evaluation, or evidence tracking.
4. Read [Knowledge and retrieval domain](domains/knowledge-retrieval.md) before changing corpora, chunking, CRAG, or GraphRAG.
5. Read [Frontend architecture](architecture/frontend.md) before changing navigation or page/API wiring.
6. Read [Testing and operations](operations/testing.md) before editing behavior that should be covered by tests or migrations.

## Notes and constraints
- The backend expects environment configuration from `.env`, with examples in `.env.example`.
- PostgreSQL is the application database, and Neo4j is used for graph-retrieval features.
- Startup code seeds baseline data after the database schema exists.
- The repository currently includes recent work on learner assistance, CRAG/GraphRAG source capture, raw document corpora, and simulation review workflows.

## Source pointers
- Backend entrypoint: `app/main.py`
- Configuration: `app/core/config.py`
- Dependency wiring: `app/core/dependencies.py`
- Frontend entrypoint: `frontend/src/main.tsx`
- Frontend routing: `frontend/src/app/router.tsx`
- Simulation route: `app/web/routes/simulations_route.py`
- Simulation service: `app/services/simulations_service.py`
- Learner service: `app/services/simulation_learner_service.py`
- Evidence ledger: `app/airag/observability/evidence_ledger.py`
