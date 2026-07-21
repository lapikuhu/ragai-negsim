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
- admin-only routes for sessions, prompts, chunking, retrieval, indexing, models, users, and graph management

This mirrors the backend's authorization model and makes the UI a useful map of the product surface.

## Important pages
- `SimulationsPage.tsx` and `SimulationCockpitPage.tsx` are the primary learner workflow pages.
- `DocumentsPage.tsx`, `DocumentDetailPage.tsx`, and `DocumentChunksPage.tsx` cover document and chunk management.
- `NotFoundPage.tsx` handles unknown routes and returns users to the dashboard.
- `CorporaPage.tsx` and `CorpusDetailPage.tsx` cover corpus management.
- `ScenariosPage.tsx`, `PersonasPage.tsx`, and `PromptsPage.tsx` support authoring and review.
- `EvaluationsPage.tsx` and `EvaluationReviewPage.tsx` are used for teacher/admin review.
- `RagEvaluationsPage.tsx` is the admin-only experiment console at `/rag-evaluations`. Admins can create, edit, delete, and enqueue complete CRAG or GraphRAG configurations, inspect each configuration's latest run and headline metrics, cancel active work, and open paginated run history.
- `RagEvaluationRunPage.tsx` is the admin-only run detail at `/rag-evaluations/runs/:runId`. It shows configuration and resolved snapshots, overall and category metrics, and filterable per-query results with answers, scores, and rank-ordered final evidence chunks.
- `KnowledgeGraphsPage.tsx`, `IndexingPage.tsx`, and `VectorStoresPage.tsx` support the retrieval infrastructure.

## Data and API wiring
The frontend consumes an OpenAPI-generated schema and typed API helpers under `frontend/src/api/`. TanStack Query features are used for list/detail fetching, invalidation, and mutation workflows.

The RAG Evaluation query layer requests the latest run independently for each visible configuration with a filtered `limit=1` request. Queued and running runs poll every two seconds, while terminal runs stop polling. History is filtered by configuration and paginated in pages of 20. A run whose latest state is `running` with stage `cleanup_pending` produces a distinct warning that queue execution is blocked until automatic GraphRAG cleanup retries succeed.

The experiment form validates the complete typed configuration before submission. GraphRAG exposes eight LLM selections: six response-pipeline roles, the RAGAS judge, and the extraction model. For CRAG, selecting reranker `none` synchronizes Top N with Top K and disables Top N.

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
