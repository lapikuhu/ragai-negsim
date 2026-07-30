# RAG Evaluation Hybrid Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give isolated CRAG RAG evaluations production-parity dense, BM25-only, and hybrid retrieval behavior and expose the controls and provenance in the admin UI.

**Architecture:** Evaluation schemas project only the seven production CRAG retrieval fields through the authoritative normalizer and keep response-model selections separate. The isolated runtime assigns stable chunk IDs and builds only the indexes required by the inferred retrieval mode, then uses production retriever factories. A reusable definition-driven field component gives profile and evaluation editors the same CRAG controls.

**Tech Stack:** FastAPI/Pydantic/SQLModel, LangChain FAISS/BM25 retrievers, React/TypeScript/TanStack Query, Vitest, pytest.

## Global Constraints

- Work on `main`; preserve the existing uncommitted documentation edit in `app/airag/evaluation/rag_eval_runtime.py`.
- Do not add endpoints or database migrations; legacy configurations need no compatibility path.
- GraphRAG evaluation remains unchanged and evaluation resources stay isolated and ephemeral.
- Use `normalize_rag_profile_config`, `get_crag_retrieval_mode`, and the shared retriever factories as the authority.
- For BM25-only, omit `retrieval_embedding_model` from normalized configurations and immutable snapshots.

---

### Task 1: Normalize the CRAG evaluation contract and final-chunk provenance

**Files:**
- Modify: `app/schemas/rag_eval_schemas.py`, `app/airag/evaluation/rag_eval_runtime.py`
- Test: `tests/unit/test_rag_eval_configuration_schemas.py`

- [ ] Write failing schema tests for dense, BM25-only, and hybrid configurations; test production defaults/bounds/reranker normalization, response-model preservation, no BM25 embedding snapshot key, and dense/BM25/fused final metadata.
- [ ] Run the focused schema tests and confirm the new assertions fail against the old `top_k`/`rewrite_limit` contract.
- [ ] Replace CRAG fields with `bm25_weight`, `dense_k`, `bm25_k`, `final_top_k`, `reranker`, `top_n`, and `max_rewrite_attempts`; normalize only those fields through the production normalizer, validate mode-dependent embedding selection, and base metric capacity on normalized final output capacity.
- [ ] Extend safe final metadata with nullable strict `dense_rank`, `bm25_rank`, and `fused_score`.
- [ ] Run `uv run pytest tests/unit/test_rag_eval_configuration_schemas.py --maxfail=1 -q` and commit the task files.

### Task 2: Build production-parity isolated CRAG adapters

**Files:**
- Modify: `app/airag/evaluation/rag_eval_runtime.py`
- Test: `tests/unit/test_rag_eval_runtime_adapters.py`, `tests/unit/test_rag_eval_full_pipeline_runtime.py`

- [ ] Write failing runtime tests asserting stable integer `document_chunk_id`, mode-specific FAISS/BM25 construction, exact shared-factory arguments, cancellation/cleanup safety, and resolved dependency/mode snapshot values.
- [ ] Run the focused runtime tests and confirm failure before implementation.
- [ ] Tag, order, and enumerate evaluation chunks once; build indexes off-thread only when their mode requires them; instantiate `make_dense_retriever`, `make_bm25_retriever`, or `make_hybrid_retriever` as appropriate; retain rank metadata through the response pipeline and final chunks.
- [ ] Run `uv run pytest tests/unit/test_rag_eval_runtime_adapters.py tests/unit/test_rag_eval_full_pipeline_runtime.py --maxfail=1 -q` and commit the task files.

### Task 3: Cover persistence and API serialization under the new contract

**Files:**
- Modify as required: `app/services/rag_eval_target_service.py`, `app/repositories/rag_eval_repo.py`, `app/schemas/rag_eval_schemas.py`
- Test: `tests/unit/test_rag_eval_api.py`, `tests/unit/test_rag_eval_repo.py`, `tests/unit/test_rag_eval_target_service.py`

- [ ] Write failing tests that create, update, enqueue, and read dense/BM25/hybrid configurations and prove hybrid provenance persists through query rows and API output.
- [ ] Run those focused tests and confirm the old serialization/snapshot behavior fails where applicable.
- [ ] Make the smallest service/repository/schema changes necessary to preserve validated snapshots and safe provenance without adding migrations or endpoints.
- [ ] Run the focused persistence/API tests and commit the task files.

### Task 4: Extract reusable definition fields and retain RAG Profile behavior

**Files:**
- Create: `frontend/src/components/rag/RagProfileDefinitionFields.tsx`
- Modify: `frontend/src/pages/RagProfilesPage.tsx`
- Test: `frontend/src/components/rag/RagProfileDefinitionFields.test.tsx`, `frontend/src/pages/RagProfilesPage.test.tsx`

- [ ] Write failing component tests for definition labels/defaults/options and both integer and float coercion.
- [ ] Run the focused frontend tests and confirm the extracted component is absent.
- [ ] Extract the definition field renderer and numeric packing helpers from the profile page; keep the profile UI's current behavior while using the shared component.
- [ ] Run the focused frontend tests and commit the task files.

### Task 5: Add definition-driven CRAG evaluation controls and provenance UI

**Files:**
- Modify: `frontend/src/pages/RagEvaluationsPage.tsx`, `frontend/src/pages/RagEvaluationRunPage.tsx`, `frontend/src/api/schema.ts`, `openwiki/domains/knowledge-retrieval.md`
- Test: `frontend/src/pages/RagEvaluationsPage.test.tsx`, `frontend/src/pages/RagEvaluationRunPage.test.tsx`

- [ ] Write failing page tests for definition loading/retry error, dense/BM25/hybrid transitions, conditional embedding selection and stale-value clearing, effective-capacity validation, summaries, and final-chunk hybrid provenance.
- [ ] Run the focused page tests and confirm the new UI behavior fails.
- [ ] Fetch CRAG definitions from `/rag-profiles/definitions`; disable editing with a retryable error until available; use the shared renderer/coercion; derive mode from `bm25_weight`; submit normalized contract values; show mode/settings and optional rank metadata.
- [ ] Regenerate OpenAPI client types with `npm run generate-api` from `frontend/`, remove the obsolete dense-only OpenWiki statement, then run the focused page tests and commit task files.

### Task 6: Verify the full implementation

**Files:**
- Modify only if verification exposes a task-scoped defect.

- [ ] Run `uv run pytest tests/unit/test_rag_eval_configuration_schemas.py tests/unit/test_rag_eval_runtime_adapters.py tests/unit/test_rag_eval_full_pipeline_runtime.py --maxfail=1 -q`.
- [ ] Run `uv run pytest tests/unit -p pytest_asyncio.plugin --maxfail=1 -q`.
- [ ] Run `npm test` and `npm run build` from `frontend/`.
- [ ] Commit any verification-only corrections.
