# Frontend Implementation Notes

Date: 2026-06-28

This file summarizes the current frontend implementation shape and the backend contract assumptions it depends on.

Last checked against:

- `frontend/openapi.json`
- `frontend/src/api/generated/schema.d.ts`
- `frontend/src/app/router.tsx`
- `frontend/src/components/layout/nav.ts`
- `frontend/src/features/*/*Queries.ts`
- `frontend/src/pages/*Page.tsx`
- `frontend/docs/backend-gaps.md`

## 1. Detected API domains

OpenAPI-backed route groups discovered from `frontend/openapi.json` and current backend routers:

- `users`
- `sessions`
- `simulations`
- `scenarios`
- `Raw Documents`
- `corpora`
- `corpus-indices`
- `document-chunks`
- `indexing-jobs`
- `prompts`
- `counterpart-personas`
- `embeddings`
- `llm-models`
- `vector-stores`
- `chunking-profiles`
- `rag-profiles`
- `knowledge-graph-indexes`
- `knowledge-graph-build-jobs`

## 2. Generated client strategy

The frontend uses:

- `openapi-typescript` to generate schema types into [../src/api/generated/schema.d.ts](../src/api/generated/schema.d.ts)
- `openapi-fetch` for runtime requests through the shared API client
- thin handwritten wrappers in `frontend/src/features/*/*Queries.ts`

This approach keeps auth headers, form-encoded login, multipart uploads, explicit JSON fallbacks, and polling behavior close to the feature that owns them.

## 3. Current route and page map

Implemented authenticated pages:

- `/`
- `/simulations`
- `/simulations/:simulationId`
- `/documents`
- `/documents/:documentId`
- `/corpora`
- `/corpora/:corpusId`
- `/settings`

Implemented teacher/admin pages:

- `/scenarios`
- `/personas`
- `/evaluations`
- `/evaluations/:simulationId/review`

Implemented admin pages:

- `/sessions`
- `/sessions/:sessionId`
- `/prompts`
- `/document-chunks`
- `/chunking-profiles`
- `/rag-profiles`
- `/knowledge-graphs`
- `/indexing`
- `/vector-stores`
- `/models`
- `/users`

Public page:

- `/login`

## 4. Reusable UI patterns

Shared patterns implemented:

- app shell with sidebar and topbar
- role-aware navigation
- loading, error, and empty states
- generic data table and pagination controls
- key-value detail cards
- status badges
- shared form fields and buttons

The negotiation cockpit uses the same layout primitives plus:

- transcript panel
- turn input panel
- right-side inspector for state and latest turn outputs
- evaluation rendering for final turn output when present

Operational admin screens add:

- polling for active indexing and knowledge graph build states
- explicit cancel/build/rebuild actions where the backend exposes them
- read-only inspection views for generated chunks, indices, and model catalogs

## 5. Authentication behavior

Authentication is implemented against the current backend contract:

- login posts `application/x-www-form-urlencoded` to `/users/login`
- access token is stored through a single auth utility
- the token is attached in the shared API fetch wrapper
- `/users/me` is used for current-user loading
- protected routes redirect unauthenticated users to `/login`
- `UserRead.roles` drives route visibility and action gating
- user registration uses `/users/register`
- role choices now load from `/users/roles` instead of being hard-coded in the user form

## 6. Schema-backed features vs disabled or gap-tracked features

Implemented directly against real endpoints:

- login and current-user auth flow
- user list, role discovery, registration, and update
- simulation list, create, start, turn submit, proxy controls, teacher review, and state display
- evaluation review workflow backed by simulation review and completed-simulation endpoints
- session list, create, heartbeat, end, and detail
- raw document list, upload, ingest, chunk, and detail
- document chunk inspection with filters
- corpus list, create, ingest, chunk, and legacy queued embed jobs
- corpus index list, detail, status, copy, update, and indexed-chunk inspection
- central indexing job queue, active-job polling, job detail polling, and cancellation
- prompt list/create/update/copy/delete
- scenario list/create/generate/update/copy/delete
- persona list/create/update/generate/delete
- chunking profile list/create/update/copy/delete and definition display
- RAG profile list/create/update/copy/delete and definition display
- vector store list/create/update/status/delete
- embedding model catalog and LLM model catalog
- knowledge graph index list/create/build/rebuild/delete with active build polling

Read-only or derived due current backend shape:

- dashboard composes simulations, raw documents, and sessions from existing list endpoints while tolerating role-based `401`/`403` responses
- corpus detail resolves from corpus list data and related corpus indices because no dedicated corpus read route exists
- evaluations page uses simulation review/completed-simulation resources, not a standalone evaluation API
- settings page is documentation-oriented because no general settings or user-preference endpoints exist
- legacy corpus embed-job queueing returns a corpus-index polling URL, while the richer job monitor exists under the newer `/indexing-jobs` workflow

## 7. Missing backend endpoints or ambiguities

Important gaps after the 2026-06-28 refresh:

- no `GET /corpora/{corpus_id}` route
- no standalone `GET /evaluations/` or `GET /evaluations/{evaluation_id}` API
- no app-level settings endpoints
- no user preference endpoints
- no dedicated dashboard summary endpoint; dashboard is composed from list endpoints
- legacy `POST /corpora/{corpus_id}/chunking-profiles/{profile_id}/vector-stores/{vector_store_id}/embed-jobs` does not expose a job-id polling resource, although `/indexing-jobs` covers the newer full indexing workflow

Resolved since the original 2026-06-05 notes:

- role metadata is available through `GET /users/roles`
- job monitoring is available through `/indexing-jobs/`, `/indexing-jobs/active`, `/indexing-jobs/{job_id}`, and `/indexing-jobs/{job_id}/cancel`

## 8. Role-gated routes and UI actions

Observed backend dependency behavior and current UI routing:

- `users` list/register/update/delete and `/users/roles`: admin
- `sessions` list/detail/create/update/end/heartbeat: admin
- `prompts`: admin
- `vector-stores`: admin
- `chunking-profiles`: admin
- `rag-profiles`: admin for mutations, authenticated users for readable profiles where the backend allows it
- `document-chunks`: admin
- `indexing-jobs`: admin
- `knowledge-graph-indexes` and `knowledge-graph-build-jobs`: admin
- `corpora`: teacher or admin for writes
- `raw-documents`: teacher or admin for create and write actions
- `scenarios`: teacher or admin for writes
- `counterpart-personas`: teacher or admin for writes
- `simulations`: authenticated users with per-simulation access checks
- `simulations/:id/review`: teacher review dependency in the backend; UI exposes evaluation routes to teacher/admin
- dashboard, documents, corpora, simulations, and settings: authenticated users

## 9. Normalized display labels for OpenAPI tags

UI label mapping:

- `Raw Documents` -> `Documents`
- `simulations` -> `Simulations`
- `sessions` -> `User Sessions`
- `counterpart-personas` -> `Personas`
- `corpus-indices` -> `Corpus Indices`
- `document-chunks` -> `Document Chunks`
- `indexing-jobs` -> `Indexing`
- `vector-stores` -> `Vector Stores`
- `chunking-profiles` -> `Chunking Profiles`
- `rag-profiles` -> `RAG Profiles`
- `knowledge-graph-indexes` -> `Knowledge Graphs`
- `knowledge-graph-build-jobs` -> `Knowledge Graph Build Jobs`
- `llm-models` -> `LLM Models`

## Verification status

Previously verified during the original implementation session:

- `npm run generate-api`
- `npm run typecheck`
- Vite dev server responded at `http://localhost:5173/`

Not rerun during the 2026-06-28 documentation refresh:

- `npm run generate-api`
- `npm run typecheck`
- `npm run test`
- production build
- browser-driven clickthrough of authenticated flows
- login with real credentials
