# Negotiation Simulator

This project is a FastAPI app for an educational negotiation simulator. The goal is to let learners practice negotiations against AI-driven counterparts, receive coaching and evaluation, and use curated corpora as grounding material for scenario-specific simulations.

The current codebase focuses on the backend foundation for:

- User authentication, roles, and sessions
- Uploading and managing raw PDF source documents
- Corpus creation, ingestion, chunking, and vector indexing
- Prompt, scenario, and counterpart persona management
- Simulation lifecycle management
- Agentic negotiation turns with coaching, counterpart response, and evaluation layers

## Purpose And Functionality

At a high level, the backend supports a workflow like this:

1. An admin or teacher uploads raw PDF material.
2. Raw documents are linked into a corpus.
3. The corpus is ingested, chunked, and embedded into a vector store.
4. Prompts, scenarios, and counterpart personas are configured.
5. A simulation is created and started for a learner.
6. The learner submits turns and the system returns counterpart responses, coach advice, and updated simulation state.

The system is designed around educational negotiation practice rather than a generic chat product. The RAG and agent graph layers are there to ground simulations in real course or domain material and to keep the negotiation flow structured.

## Folder Structure

```text
ragai-negsim/
+-- app/
|   +-- airag/             # RAG, agent graphs, embeddings, retrieval, vector store logic
|   +-- core/              # Settings, auth/security, shared FastAPI dependencies
|   +-- db/                # Database engine/session setup and startup seeding
|   +-- models/            # SQLModel ORM models
|   +-- repositories/      # Persistence and query layer
|   +-- schemas/           # Pydantic/SQLModel request-response schemas
|   +-- services/          # Application/business logic
|   +-- web/routes/        # FastAPI route modules
|   +-- main.py            # FastAPI application entrypoint
+-- chroma_db/             # Local Chroma persistence used in development
+-- docs/                  # Specs and planning notes
+-- migrations/            # Alembic environment and migration versions
+-- scripts/               # Local scripts and utilities
+-- tests/                 # Automated test suite
+-- pyproject.toml         # Project metadata and dependencies
+-- requirements.txt       # Flat dependency export
+-- uv.lock                # uv lockfile
```

## Stack Used So Far

- Python 3.12+
- FastAPI
- SQLModel and SQLAlchemy async
- PostgreSQL via `psycopg`
- JWT auth with `python-jose`
- LangChain
- LangGraph
- Chroma, FAISS, and PGVector integration points for vector storage
- Docling and PyPDF-based PDF ingestion/parsing
- Neo4j integration hooks for graph-store work
- Pytest and pytest-asyncio
- `uv` for dependency and environment management

## Assumptions And Conventions

- Imports use package-qualified paths such as `app.services...` and `app.web.routes...`.
- The backend assumes PostgreSQL is the system of record for application data.
- The backend also expects Neo4j connection settings to be available, even if a given local flow does not actively use graph features.
- Raw document upload currently assumes PDF input.
- Uploaded raw documents are stored on disk under `RAW_DOCS_DIR`, configured in `.env`.
- Local frontend development is expected to run from `localhost` or `127.0.0.1` on ports `3000`, `4173`, `5173`, or `8000`; those origins are enabled in CORS.
- Corpus embedding builds can run synchronously or be queued as FastAPI background tasks.
- FastAPI startup currently seeds fixed roles and an admin user after the database schema already exists.

## Installation

### 1. Clone the repository

```powershell
git clone <your-repo-url>
cd ragai-negsim
```

### 2. Install Python dependencies

Using `uv`:

```powershell
uv sync
```

If Alembic is not already available in your environment, install it as well:

```powershell
uv add alembic
```

If you prefer `pip`:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install alembic
```

### 3. Configure environment variables

Create or replace `.env` with your own local values. At minimum, configure:

- `ASYNC_DATABASE_URL`
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `SECRET_KEY`
- `ALGORITHM`
- `OPENAI_API_KEY`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `RAW_DOCS_DIR`
- `HF_TOKEN`

Example shape:

```env
ASYNC_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/negotiation_sim
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-neo4j-password
SECRET_KEY=replace-this
ALGORITHM=HS256
OPENAI_API_KEY=replace-this
ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace-this
RAW_DOCS_DIR=app/airag/raw_docs
HF_TOKEN=replace-this
```

## Database Setup

### Instantiate the application database

Create the PostgreSQL database itself before starting the app. For example:

```sql
CREATE DATABASE negotiation_sim;
```

After the database exists and your `.env` points to it, the FastAPI startup hook will seed fixed roles and the configured admin user.

### Alembic and schema versioning

This repository now includes:

- `alembic.ini` at the repo root
- `migrations/env.py`
- `migrations/script.py.mako`
- `migrations/versions/` for generated revision files

The Alembic environment reads the application settings from `.env`, imports the SQLModel metadata from the `app.models` modules, and converts the async application database URL into a synchronous SQLAlchemy URL for migration execution.

Typical workflow:

```powershell
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

To roll back one revision:

```powershell
alembic downgrade -1
```

To inspect the current revision:

```powershell
alembic current
```

The backend startup code in [app/db/db.py](/c:/Users/iason/Documents/PYTHON_PROJECTS/ragai-negsim/app/db/db.py:73) assumes the schema has already been created and migrated before the app starts.

## Starting FastAPI

Day-0 alembic versioning:
```powershell
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Run the API with the package entrypoint:

```powershell
uv run uvicorn app.main:app --reload
```

Default local URL:

```text
http://127.0.0.1:8000
```

## API Documentation

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

ReDoc:

```text
http://127.0.0.1:8000/redoc
```

## Main API Areas

- `/users` for registration, login, identity, and user administration
- `/sessions` for session lifecycle and heartbeat management
- `/raw-documents` for PDF upload and source document management
- `/corpora` for corpus creation, ingestion, chunking, and embedding jobs
- `/corpus-indices` for index metadata and build status
- `/chunking-profiles` for chunking presets
- `/vector-stores` for vector backend configuration
- `/prompts` for coach, counterpart, and evaluator prompt management
- `/scenarios` for negotiation scenarios
- `/counterpart-personas` for counterpart configuration
- `/simulations` for simulation creation, startup, turn submission, cancellation, and review

## Testing

Run the full test suite:

```powershell
uv run pytest
```

The repository currently includes service-level coverage as well as an API-level smoke test for:

- login
- raw document upload
- corpus creation
- corpus index queueing
- simulation start
- simulation turn submission

## Frontend

A React + Vite frontend now lives in [frontend/README.md](/c:/Users/iason/Documents/PYTHON_PROJECTS/ragai-negsim/frontend/README.md:1).

Typical local setup:

1. Start FastAPI from the repository root:

```powershell
uv run uvicorn app.main:app --reload
```

2. Start Vite from `frontend/`:

```powershell
cd frontend
npm install
npm run dev
```

Development URLs:

- Frontend app: `http://localhost:5173/`
- Backend API: `http://127.0.0.1:8000`

During development, open the frontend in the browser at `http://localhost:5173/`.
The React app uses the Vite proxy to forward supported relative API requests such as `/users/me` and `/simulations/` to the FastAPI backend at `http://127.0.0.1:8000`.
You should browse to the frontend URL, not the backend URL, for normal UI work.
