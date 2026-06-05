# Frontend Implementation Notes

Date: 2026-06-05

## 1. Detected API domains

OpenAPI-backed route groups discovered from `frontend/openapi.json`:

- `users`
- `sessions`
- `simulations`
- `scenarios`
- `Raw Documents`
- `corpora`
- `corpus-indices`
- `prompts`
- `counterpart-personas`
- `embeddings`
- `vector-stores`
- `chunking-profiles`

## 2. Generated client strategy

The frontend uses:

- `openapi-typescript` to generate schema types into [schema.d.ts](/c:/Users/iason/Documents/PYTHON_PROJECTS/ragai-negsim/frontend/src/api/generated/schema.d.ts:1)
- `openapi-fetch` for runtime requests
- thin handwritten wrappers in `frontend/src/features/*/*Queries.ts`

This approach was chosen over Orval so auth headers, form-encoded login, and multipart uploads stay explicit and easy to evolve as the backend grows.

## 3. Proposed route and page map

Implemented pages:

- `/login`
- `/`
- `/simulations`
- `/simulations/:simulationId`
- `/documents`
- `/documents/:documentId`
- `/corpora`
- `/corpora/:corpusId`
- `/evaluations`
- `/settings`
- `/sessions`
- `/sessions/:sessionId`
- `/prompts`
- `/personas`
- `/scenarios`
- `/models`
- `/users`

Role-gated routes:

- `admin`: sessions, prompts, models, users
- `teacher|admin`: scenarios, personas
- authenticated users: dashboard, simulations, documents, corpora, evaluations, settings

## 4. Reusable UI patterns

Shared patterns implemented:

- app shell with sidebar and topbar
- loading, error, and empty states
- generic data table
- key-value detail cards
- status badges
- shared form fields and buttons

The negotiation cockpit uses the same layout primitives plus:

- transcript panel
- turn input panel
- right-side inspector for state and latest turn outputs

## 5. Authentication behavior

Authentication is implemented against the existing backend contract:

- login posts `application/x-www-form-urlencoded` to `/users/login`
- access token is stored through a single auth utility
- the token is attached in the shared API fetch wrapper
- `/users/me` is used for current-user loading
- protected routes redirect unauthenticated users to `/login`
- `UserRead.roles` drives route visibility and action gating

## 6. Schema-backed features vs disabled or gap-tracked features

Implemented directly against real endpoints:

- login and current-user auth flow
- simulation list, create, start, turn submit, teacher review, and state display
- session list, create, heartbeat, end, and detail
- raw document list, upload, ingest, chunk, and detail
- corpus list, create, ingest, chunk, and queued embed jobs
- prompt list/create/update
- scenario list/create/update
- persona list/create/update
- model screens from embeddings, chunking profiles, vector stores, and corpus indices
- user list and user registration

Read-only or derived due current backend shape:

- evaluations page derives review-like signals from simulations
- corpus detail resolves from corpus list data because no dedicated corpus read route exists
- settings page is documentation-oriented because no general settings endpoints exist

## 7. Missing backend endpoints or ambiguities

Important gaps discovered during implementation:

- no `GET /corpora/{corpus_id}` route
- no standalone evaluations API
- no embedding job polling or job listing route for queued corpus embedding jobs
- no app-level settings endpoints
- no dedicated dashboard endpoints; dashboard is composed from existing list endpoints

## 8. Role-gated routes and UI actions

Observed backend dependency behavior:

- `users` list/register/update/delete: admin
- `sessions` list/detail/create/update/end/heartbeat: admin
- `prompts`: admin
- `vector-stores`: admin
- `chunking-profiles`: admin
- `corpora`: teacher or admin for writes
- `raw-documents`: teacher or admin for create and write actions
- `scenarios`: teacher or admin for writes
- `counterpart-personas`: teacher or admin for writes
- `simulations`: authenticated users with per-simulation access checks
- `simulations/:id/review`: teacher

## 9. Normalized display labels for OpenAPI tags

UI label mapping:

- `Raw Documents` -> `Documents`
- `simulations` -> `Simulations`
- `sessions` -> `User Sessions`
- `counterpart-personas` -> `Personas`
- `corpus-indices` -> `Corpus Indices`
- `vector-stores` -> `Vector Stores`
- `chunking-profiles` -> `Chunking Profiles`

## Verification status

Verified in this session:

- `npm run generate-api`
- `npm run typecheck`
- Vite dev server responds at `http://localhost:5173/`

Not yet fully verified in-session:

- production build, because sandbox restrictions blocked `vite build`
- browser-driven clickthrough of authenticated flows
- login with real credentials
