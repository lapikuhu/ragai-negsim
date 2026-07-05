# Frontend architecture

The frontend is a React + TypeScript application that mirrors the backend's major domains. It uses React Router for navigation, TanStack Query for server-state management, and an authenticated app shell for protected routes.

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
- `CorporaPage.tsx` and `CorpusDetailPage.tsx` cover corpus management.
- `ScenariosPage.tsx`, `PersonasPage.tsx`, and `PromptsPage.tsx` support authoring and review.
- `EvaluationsPage.tsx` and `EvaluationReviewPage.tsx` are used for teacher/admin review.
- `KnowledgeGraphsPage.tsx`, `IndexingPage.tsx`, and `VectorStoresPage.tsx` support the retrieval infrastructure.

## Data and API wiring
The frontend consumes an OpenAPI-generated schema and typed API helpers under `frontend/src/api/`. TanStack Query features are used for list/detail fetching, invalidation, and mutation workflows.

The recent UI history shows the frontend tracking backend domain changes closely, including learner debug traces, raw document corpus associations, simulation learner settings, and pagination controls for document chunks.

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
