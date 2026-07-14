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

The Vite dev server proxies supported API paths to that backend through [vite.config.ts](vite.config.ts).

## Run the dev server

For the complete local application, start from the repository root:

```powershell
python scripts/dev.py
```

The launcher requires Python 3.12+, uv, Node/npm, a configured root `.env`, reachable PostgreSQL and Neo4j instances, and a valid OpenAI key for first-time scenario seeding. It runs locked dependency installation, migrations, and starter-data seeding before starting both development servers.

For frontend-only troubleshooting after the backend is already running, use:

```powershell
npm ci
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
- updates [openapi.json](openapi.json)
- regenerates [schema.d.ts](src/api/generated/schema.d.ts)

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

- [implementation-notes.md](docs/implementation-notes.md)
- [backend-gaps.md](docs/backend-gaps.md)
