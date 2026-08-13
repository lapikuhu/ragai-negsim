# Frontend architecture

The frontend is a React + TypeScript application that mirrors the backend's major domains. It uses React Router for navigation, TanStack Query for server-state management, and an authenticated app shell for protected routes. The router now ends with a catch-all 404 page (`NotFoundPage`) for unknown paths.

## Entry points
- `frontend/src/main.tsx` bootstraps React, the query client, authentication, and routing.
- `frontend/src/app/router.tsx` defines the page map and role-gated navigation.
- `frontend/src/app/AuthProvider.tsx` provides authentication state.
- `frontend/src/app/ProtectedRoute.tsx` enforces logged-in and role-restricted access.

## Route structure
The router is organized into three main access tiers:
- public login route
- protected routes available to authenticated users
- teacher/admin routes for review and scenario management
- admin-only routes for sessions, prompts, chunking, retrieval, full corpus index pipe jobs, models, users, and graph management

This mirrors the backend's authorization model and makes the UI a useful map of the product surface.

## Important pages
- `SimulationsPage.tsx` and `SimulationCockpitPage.tsx` are the primary learner workflow pages. Simulation creation places the RAG profile after the corpus and derives its required artifact bindings from that profile: dense CRAG requires a built dense index, BM25 CRAG requires a built BM25 index, hybrid CRAG requires both compatible artifacts, and GraphRAG retains its graph-bound dense index behavior.
- `DocumentsPage.tsx`, `DocumentDetailPage.tsx`, and `DocumentChunksPage.tsx` cover document and chunk management.
- `NotFoundPage.tsx` handles unknown routes and returns users to the dashboard.
- `CorporaPage.tsx` and `CorpusDetailPage.tsx` cover corpus management.
- Corpus detail now embeds the BM25 artifacts card, which combines the built
  BM25 artifact list, the persisted chunk-set picker, and corpus-scoped BM25
  build-job history. Admins can queue a build for one persisted chunk set,
  cancel active work, and retry failed or cancelled jobs. Corpora without
  persisted chunks link to the Full Corpus Index Pipe, which is still the
  exposed way to produce chunks.
- `ScenariosPage.tsx`, `PersonasPage.tsx`, and `PromptsPage.tsx` support authoring and review.
- `EvaluationsPage.tsx` and `EvaluationReviewPage.tsx` are used for teacher/admin review.
- `RagEvaluationsPage.tsx` is the admin-only experiment console at `/rag-evaluations`. Admins can create, edit, delete, and enqueue complete CRAG or GraphRAG configurations, inspect each configuration's latest run and headline metrics, cancel active work, and open paginated run history. The page now keeps latest-run polling independent per visible configuration, uses the shared `formatRagEvalProgress()` helper for status text, and surfaces a queue-blocked warning when any running run is stuck in `cleanup_pending`.
- `RagEvaluationRunPage.tsx` is the admin-only run detail at `/rag-evaluations/runs/:runId`. It shows configuration and resolved snapshots, overall and category metrics, and filterable per-query results with answers, scores, and rank-ordered final evidence chunks. Successfully completed runs expose an Export CSV action for run metadata, configuration and resolved-pipeline snapshots, and overall/category metrics. The run detail also has a dedicated cleanup-pending warning and a failure banner when a run ends in `failed`, and it reuses the same progress formatter for scoring-stage messaging.
- `KnowledgeGraphsPage.tsx`, `FullCorpusIndexPipeJobsPage.tsx`, and `VectorStoresPage.tsx` support the retrieval infrastructure.

## Data and API wiring
The frontend consumes an OpenAPI-generated schema and typed API helpers under `frontend/src/api/`. TanStack Query features are used for list/detail fetching, invalidation, and mutation workflows. The BM25 metadata query uses the admin-only `GET /corpus-bm25-indices/` list endpoint and never requests serialized artifact bytes. The new `RagProfileDefinitionFields` component centralizes CRAG field rendering, retrieval-mode badges, and mode-dependent disabling so Rag Profiles and evaluation forms stay aligned with the backend's dense, BM25, and hybrid artifact rules.

The RAG Evaluation query layer requests the latest run independently for each visible configuration with a filtered `limit=1` request. Queued and running runs poll every two seconds, while terminal runs stop polling. History is filtered by configuration and paginated in pages of 20. A run whose latest state is `running` with stage `cleanup_pending` produces a distinct warning that queue execution is blocked until automatic GraphRAG cleanup retries succeed, and the form submission path now blocks duplicate in-flight submissions.

The experiment form validates the complete typed configuration before submission. GraphRAG exposes eight LLM selections: six response-pipeline roles, the RAGAS judge, and the extraction model. CRAG reuses the RAG-profile definition renderer for BM25 weight, dense and BM25 candidate limits, final fusion limit, reranker, reranked count, and rewrite attempts. Retrieval mode disables irrelevant candidate controls; reranker `none` synchronizes and disables the reranked count. BM25-only evaluation disables and omits the retrieval embedding model, while dense and hybrid evaluation require it.

The recent UI history shows the frontend tracking backend domain changes closely, including learner debug traces, raw document corpus associations, document bibliographic metadata in list/detail views, simulation learner settings, coach source cards, and pagination controls for document chunks.

## What to watch out for
- Page titles and routes are tightly coupled to backend domain names, so route renames usually require API and test updates too.
- The sidebar hides some sections by role, so a new page may need navigation updates as well as routing changes.
- Some pages have dedicated tests; use them as a guide for user-visible behavior.

## Relevant tests and checks
- `frontend/src/pages/*.test.tsx`
- `frontend/src/app/viteProxyConfig.test.ts`
- `frontend/src/components/layout/Sidebar.test.tsx`
- `frontend/src/utils/pagination.test.ts`
- `frontend/src/utils/paginationHook.test.tsx`

## Source pointers
- `frontend/src/main.tsx`
- `frontend/src/app/router.tsx`
- `frontend/src/app/AuthProvider.tsx`
- `frontend/src/app/ProtectedRoute.tsx`
- `frontend/src/components/layout/AppShell.tsx`
- `frontend/src/components/layout/Sidebar.tsx`
