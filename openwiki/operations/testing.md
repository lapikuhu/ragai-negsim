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
- `tests/unit/test_rag_eval_chunking.py` covers synthetic chunking dispatch and alignment metadata for the evaluation corpus.
- `tests/unit/test_rag_eval_strategies.py` covers the isolated strategy registry and rejection of unsupported RAG evaluation modes.
- `tests/unit/test_rag_eval_suite.py` fixes the versioned suite at 80 examples with the exact category distribution, paired files, multi-document evidence, precise locators, and deterministic hashing.
- `tests/unit/test_rag_eval_configuration_schemas.py` covers complete typed CRAG/GraphRAG configurations, normalization, and cross-field validation.
- `tests/unit/test_rag_eval_runtime_adapters.py` and `tests/unit/test_rag_eval_full_pipeline_runtime.py` cover isolated resources, the shared canonical response pipeline, final contexts, progress, cancellation, and cleanup.
- `tests/unit/test_rag_eval_metrics.py` covers final-context Hit/MRR, unanswerable abstention/false positives, five RAGAS metrics, and overall/category aggregation.
- `tests/unit/test_rag_eval_repo.py` covers immutable snapshots, FIFO claims, the one-running invariant, queued cancellation, transitions, and atomic finalization.
- `tests/unit/test_rag_eval_coordinator.py` and `tests/unit/test_rag_eval_target_service.py` cover durable coordination, restart recovery, cleanup blocking, progress, cancellation, and service behavior.
- `tests/unit/test_rag_eval_api.py` covers the exact admin-only configuration/run routes, pagination and filters, response codes, and sanitized errors.
- `tests/unit/test_rag_eval_legacy_cleanup.py` prevents transitional pair-profile and first-generation runtime imports or routes from returning.
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
- RAG-evaluation coordinator tests assume one Uvicorn worker; multi-process ownership requires a separate leader-election design
- simulation changes usually require service, route, and graph tests
- frontend page changes usually require page tests and router/sidebar updates
- config or dependency changes often require startup or auth tests

## Source pointers
- `tests/`
- `scripts/seeder.py`
- `scripts/flushdb.py`
- `migrations/env.py`
- `alembic.ini`
