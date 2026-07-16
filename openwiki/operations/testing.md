# Testing and operations

This repository has a substantial automated test suite and several operational scripts. Future changes should usually touch both code and tests because many business rules are already asserted directly.

## Test strategy
The project uses pytest for backend coverage and component/page tests in the frontend.

### Backend tests
Backend tests cover:
- route behavior
- service logic
- repository and schema behavior
- negotiation graph routing
- retrieval, synthetic evaluation, and evidence ledger behavior
- authentication and role boundaries
- startup and seed scripts
- PostgreSQL and Neo4j integration paths when real services are available

### Frontend tests
Frontend tests cover:
- route rendering
- page behavior
- pagination helpers
- sidebar and layout behavior
- API wiring and proxy behavior

## High-signal backend test files
- `tests/unit/test_simulations_service.py`
- `tests/unit/test_simulation_learner_service.py`
- `tests/unit/test_negotiation_graph.py`
- `tests/unit/test_evidence_ledger.py`
- `tests/unit/test_crag_grounding.py`
- `tests/unit/test_graphrag_retrieval.py`
- `tests/unit/test_rag_eval_helpers.py`
- `tests/unit/test_ragas_helpers.py`
- `tests/unit/test_rag_eval_retrieval_config.py` covers retrieval-config validation, GraphRAG pair creation requirements, and snapshotting the pair config onto a run.
- `tests/unit/test_rag_eval_runtime.py` covers the shared in-memory corpus adapters, selected retrieval embeddings, GraphRAG's scoped graph build, and success/failure cleanup.
- `tests/unit/test_rag_eval_answer_generation.py` covers the grounded-answer prompt, abstention path, and cancellation-aware answer generation.
- `tests/unit/test_rag_eval_service.py` covers persisted evaluation stages (`chunking`, `building_graph`, `retrieving`, `generating_answer`, `judging`, `finished`) and recovery when temporary GraphRAG cleanup must be retried.
- `tests/unit/test_raw_documents_service.py`
- `tests/unit/test_document_chunks_service.py`
- `tests/unit/test_langsmith_traceable_boundaries.py`
- `tests/unit/test_alpha_smoke_api.py`
- `tests/integration/test_postgres_migrations.py`
- `tests/integration/test_postgres_startup_seed.py`
- `tests/integration/test_postgres_async_session.py`
- `tests/integration/test_neo4j_scoped_store.py`

## Operational scripts
- `scripts/seeder.py` seeds roles, users, scenarios, personas, chunking profiles, and vector-store configs.
- `scripts/flushdb.py` clears local data during development.
- `scripts/bootstrap.py` provides bootstrap support.
- `scripts/scenarios.py` and `scripts/personas.py` are larger content-generation helpers.

## Migrations
Alembic is configured at the repository root via `alembic.ini` and `migrations/env.py`.

When changing database-backed models or schemas:
1. update the model/schema/service code
2. generate or edit the migration
3. run the relevant service/API tests
4. verify the app still starts with seeded data

## Environment and local setup notes
- Use `.env.example` as the configuration template; do not treat `.env` as documentation because it may contain secrets.
- PostgreSQL is expected for the main app data store.
- Neo4j is required for graph retrieval features.
- `RAW_DOCS_DIR` controls where uploaded raw documents are written on disk.
- LangSmith tracing is optional but wired through `app/core/config.py`.
- Integration tests set default placeholders for PostgreSQL, Neo4j, admin auth, and OpenAI settings in `tests/integration/conftest.py`; they skip cleanly if the services are unreachable.

## When editing behavior
Use the tests to decide how far a change must propagate:
- retrieval changes usually require evidence-, grounding-, and evaluation-related tests
- GraphRAG evaluation changes must confirm that the temporary Neo4j scope is removed on success, failure, cancellation/recovery, and that a failed recovery cleanup leaves the run retryable rather than terminalizing it
- simulation changes usually require service, route, and graph tests
- frontend page changes usually require page tests and router/sidebar updates
- config or dependency changes often require startup or auth tests

## Source pointers
- `tests/`
- `scripts/seeder.py`
- `scripts/flushdb.py`
- `migrations/env.py`
- `alembic.ini`
