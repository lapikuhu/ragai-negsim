# Frontend

This folder contains the React + Vite + TypeScript frontend for the Negotiation Simulator backend.

## Stack

- React
- Vite
- TypeScript
- Tailwind CSS
- TanStack Query
- `openapi-typescript`
- `openapi-fetch`

## Backend URL

Development expects the FastAPI backend at:

```text
http://127.0.0.1:8000
```

The Vite dev server proxies supported API paths to that backend through [vite.config.ts](ragai-negsim/frontend/vite.config.ts:1).

## Install dependencies

From the `frontend/` directory:

```powershell
npm install
```

## Run the dev server

Start the backend from the repository root:

```powershell
uv run uvicorn app.main:app --reload
```

Start the frontend from `frontend/`:

```powershell
npm run dev
```

Default local frontend URL:

```text
http://localhost:5173/
```

## Regenerate the API client

The backend OpenAPI schema is the source of truth.

From `frontend/`:

```powershell
npm run generate-api
```

This command:

- fetches `http://127.0.0.1:8000/openapi.json`
- updates [openapi.json](ragai-negsim/frontend/openapi.json:1)
- regenerates [schema.d.ts](ragai-negsim/frontend/src/api/generated/schema.d.ts:1)

## Typecheck

```powershell
npm run typecheck
```

## Production build

```powershell
npm run build
```

## Current capabilities

Implemented against real backend endpoints:

- login and current-user auth
- dashboard from live list endpoints
- simulations list, create, start, turn submit, and teacher review
- session admin pages
- raw document upload, ingest, chunk, and detail
- corpus list, create, ingest, chunk, and queued embedding jobs
- prompts, personas, and scenarios management
- models and vector-store inspection
- user list and registration

## Known backend gaps

See:

- [implementation-notes.md](ragai-negsim/frontend/docs/implementation-notes.md:1)
- [backend-gaps.md](ragai-negsim/frontend/docs/backend-gaps.md:1)
