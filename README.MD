# Negotiation Simulator

This project is a demonstration  FastAPI app for an educational agentic negotiation simulator, and is part of the Athens University of Economics and Business AI for Developers: Design, Build, Deploy LLM-powered Applications 2026 cohort (https://diaviou.aueb.gr/programs/36148-AI-for-Developers--Design,-Build,-Deploy-LLM-powered-Applications-1001200). The goal is to let learners practice negotiations against AI-driven counterparts, receive coaching and evaluation, and use curated corpora as grounding material for scenario-specific simulations.

Developed on win32.

The current codebase focuses on the backend foundation for:

- User authentication, roles, and sessions
- Uploading and managing raw PDF source documents
- Corpus creation, ingestion, chunking, and vector indexing
- Reusable retrieval strategies with both CRAG and GraphRAG flows
- Prompt, scenario, and counterpart persona management
- Simulation lifecycle management
- Agentic negotiation turns with coaching, counterpart response, learning assistant, and evaluation layers

## Purpose And Functionality

At a high level, the backend supports a workflow like this:

1. An admin or teacher uploads raw PDF material.
2. Raw documents are linked into a corpus.
3. The corpus is ingested, chunked, and embedded into a vector store.
4. Prompts, scenarios, and counterpart personas are configured.
5. A simulation is created and started for a learner.
6. The learner submits turns and the system returns counterpart responses, coach advice, and updated simulation state.

### Generative AI Features

The system is designed around educational negotiation practice rather than a generic chat product. The RAG and agent graph layers are there to ground simulations in real course or domain material and to keep the negotiation flow structured.

The generative-AI layer is built from three cooperating parts:

- Retrieval profiles define how course or domain material is selected for a simulation.
- LangGraph-based agent graphs coordinate negotiation turns, coaching, counterpart responses, and evaluation.
- Prompt templates keep each model call role-specific and aligned with the simulation context.

Two retrieval strategies are currently available through reusable RAG profiles:

- `CRAG` for corrective retrieval over the configured vector store. The CRAG graph retrieves candidate chunks, reranks them, grades their relevance, rewrites the query when evidence is weak, generates an answer from trusted context, checks answer quality, and falls back when the configured rewrite limit is reached.
- `GraphRAG` for knowledge-graph retrieval backed by Neo4j. GraphRAG uses a built knowledge graph tied to a corpus index and can retrieve scoped evidence through semantic graph search, validated text-to-Cypher, or a hybrid mode that combines ranked evidence with reciprocal rank fusion.

RAG profiles expose strategy-specific settings instead of hard-coding retrieval behavior. CRAG profiles configure values such as retrieved document count, reranker choice, reranked document count, and maximum rewrite attempts. GraphRAG profiles configure retrieval mode, evidence limits, traversal depth, and the hybrid ranking constant.

The parent negotiation graph orchestrates each turn through dedicated agent nodes:

- Intent classification decides whether the learner's input should continue the negotiation or move toward final evaluation.
- The counterpart node produces the AI counterpart's negotiation response.
- The rolling evaluator assesses the current turn while the simulation is still active.
- The coach node returns learner-facing guidance after the counterpart and evaluator have run.
- The final evaluator produces closing assessment when the negotiation reaches the final path.
- User can assign the negotiation to a proxy negotiator graph outside the main simulation graph, either for a single turn or for the whole negotiation.
- At any given time, the user can ask a learning assistant autonomous agent for general advise on negotiation practice and theory. The agent has its own tools and decides which ones to use.

Retrieval is injected into the coaching and evaluation paths so feedback can be grounded in uploaded corpus material rather than relying only on conversation history. The counterpart remains persona- and scenario-driven, while coaching and evaluation can use retrieved evidence to support more specific advice and assessment.

All agent and graph node prompts follow the Persona, Task, Context, Format (PTCF) framework. This keeps prompts explicit about role, job, grounding context, and output shape, which makes prompt changes easier to review and reduces accidental drift between counterpart, coach, evaluator, and classifier behavior.

LangSmith tracing and the internal evidence ledger are used around the RAG and negotiation graphs so generated outputs can be inspected with the retrieval context, graph metadata, and evidence used during a turn.

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
- LangSmith for tracing
- Chroma, FAISS, and PGVector integration points for vector storage
- Docling and PyPDF-based PDF ingestion/parsing
- Neo4j integration hooks for graph-store work
- Pytest and pytest-asyncio
- `uv` for dependency and environment management

## Assumptions And Conventions

- Imports use package-qualified paths such as `app.services...` and `app.web.routes...`.
- The backend assumes PostgreSQL is the system of record for application data.
- The backend also expects Neo4j connection settings to be available, even if a given local flow does not actively use graph features.
- Any Neo4j instance used for knowledge graph builds must have the APOC plugin enabled because the graph-store integration depends on APOC procedures during schema refresh and persistence.
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

Copy `.env.example` with your own local values in your `.env` file. At minimum, configure:

- `ASYNC_DATABASE_URL`
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `SECRET_KEY`
- `ALGORITHM`
- `OPENAI_API_KEY`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `HF_TOKEN`

If you plan to use knowledge graph features, make sure the target Neo4j DBMS has the APOC plugin enabled before running a build.

Example full shape in the .env.example file.

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

The backend startup code in [app/db/db.py] assumes the schema has already been created and migrated before the app starts.

### Seed starter data

After applying the migrations, newcomers can populate the database with useful
starter records by running the seeder from the repository root:

```powershell
uv run python scripts/seeder.py
```

The seeder creates the configured admin account and fixed roles, sample student
and teacher users, negotiation scenarios, counterpart personas, chunking
profiles, and vector-store configurations. Scenario creation uses the configured
OpenAI model, so `OPENAI_API_KEY` must be valid.


To rebuild the database from scratch and then seed starter data in one step,
run:

```powershell
uv run python scripts/flushdb.py
uv run python scripts/seeder.py
```

This drops all existing tables, recreates the schema from the registered
SQLModel metadata, and then runs the normal seeder.

### Demo Raw Documents

Demo pdf are provided under the demo_docs folder. These are publicly available reports from the Program On Negotiation of the Harvard Law of School: https://www.pon.harvard.edu/

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

If you want to monitor only the FastAPI app:
```powershell
uv run uvicorn app.main:app --reload --reload-dir app
```

or exclude annoying logger changes:
```powershell
uv run uvicorn app.main:app --reload --reload-dir app --reload-exclude "logs/*"
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

## App DOC

Greek DOC file in docs\DOC.pdf

## Main API Areas

- `/users` for registration, login, identity, and user administration
- `/sessions` for session lifecycle and heartbeat management
- `/raw-documents` for PDF upload and source document management
- `/corpora` for corpus creation, ingestion, chunking, and embedding jobs
- `/corpus-indices` for index metadata and build status
- `/knowledge-graph-indexes` for GraphRAG graph definitions and build jobs
- `/chunking-profiles` for chunking presets
- `/vector-stores` for vector backend configuration
- `/rag-profiles` for reusable CRAG and GraphRAG retrieval strategies
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

Authored by CODEX.

A React + Vite frontend now lives in [frontend/README.md]

Typical local setup:

1. Start FastAPI from the repository root:

```powershell
uv run uvicorn app.main:app --reload
```
or
```powershell
uv run uvicorn app.main:app --reload --reload-dir app
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

## Docker Deployment Strategy

The repository includes a Compose-based deployment scaffold for running the
backend, frontend, PostgreSQL, and Neo4j together in containers.

Current deployment files:

- [Dockerfile](Dockerfile) builds the FastAPI backend image.
- [compose.yaml](compose.yaml) defines the frontend, backend, PostgreSQL, and Neo4j services.
- [frontend/Dockerfile](frontend/Dockerfile) builds the React app and serves it with Nginx.
- [frontend/nginx.conf](frontend/nginx.conf) serves the built frontend with React Router fallback.
- [.dockerignore](.dockerignore) and [frontend/.dockerignore](frontend/.dockerignore) keep local caches, secrets, build output, and runtime data out of Docker build contexts.

The current Docker setup intentionally uses separate public ports instead of a
single reverse proxy:

- Frontend UI: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- PostgreSQL: `localhost:5432`
- Neo4j Browser: `http://localhost:7474`
- Neo4j Bolt: `localhost:7687`

### Container Roles

- `frontend` builds `frontend/` with `npm ci` and `npm run build`, then serves `dist/` from Nginx.
- `backend` installs Python runtime dependencies with `uv sync --frozen --no-dev --no-install-project` and starts `uvicorn app.main:app`.
- `postgres` stores application data in a named Docker volume.
- `neo4j` runs the community Neo4j image with the APOC plugin enabled for GraphRAG features.

Persistent runtime data is stored in named Docker volumes:

- `postgres-data` for PostgreSQL data
- `neo4j-data`, `neo4j-logs`, and `neo4j-plugins` for Neo4j
- `raw-docs` for uploaded source documents
- `app-logs` for backend logs
- `chroma-data` for local Chroma persistence

### Environment Configuration

Docker Compose reads variables from the shell and from a root `.env` file when
present. Do not commit real secrets.

At minimum, configure the same core values used by the local app:

- `SECRET_KEY`
- `ALGORITHM`
- `ADMIN_USERNAME`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `OPENAI_API_KEY`
- `HF_TOKEN`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`

The backend container receives Docker-native service URLs from Compose:

- `ASYNC_DATABASE_URL=postgresql+asyncpg://...@postgres:5432/...`
- `NEO4J_URI=neo4j://neo4j:7687`
- `RAW_DOCS_DIR=/app/data/raw_docs`

For local Ollama access from inside Docker, use `DOCKER_OLLAMA_BASE_URL`. The
default is `http://host.docker.internal:11434`.

The frontend uses Vite, so `VITE_API_BASE_URL` is baked into the frontend image
at build time. For local Compose, the default is:

```powershell
VITE_API_BASE_URL=http://localhost:8000
```

For a remote host, set `VITE_API_BASE_URL` to the browser-reachable backend URL
before building the frontend image.

### Build And Run

Validate the Compose file without expanding local secrets:

```powershell
docker compose -f compose.yaml config --no-interpolate
```

Build the images:

```powershell
docker compose build
```

Start PostgreSQL and Neo4j first:

```powershell
docker compose up -d postgres neo4j
```

Apply database migrations before starting the backend app:

```powershell
docker compose run --rm backend alembic upgrade head
```

Then start the backend and frontend:

```powershell
docker compose up -d backend frontend
```

To inspect service status:

```powershell
docker compose ps
```

To stop the stack while keeping named volumes:

```powershell
docker compose down
```

### Current Boundaries

- Migrations are explicit and are not run automatically by the backend startup command.
- The frontend is served by its own Nginx container; Nginx is not acting as a reverse proxy for the backend.
- Backend health checks currently verify TCP connectivity to port `8000`, not an application-level `/health` endpoint.
- PostgreSQL and Neo4j ports are exposed to the host for local development convenience.
- Docker image builds require Docker Desktop or another Docker engine with Linux containers enabled.

## Typical User Worfklow

### Admin

- Creates users in the Users section
- Creates chunking profiles, where different chunkers can be defined for the ingestion process.
- Creates configurable vector stores that will be used for indexing
- Uploads raw documents (pdfs only). They are stored locally under /raw_docs_store
- Defines a corpus from uploaded documents
- With a corpus, chunking profile and a vector store, admin can create a corpus index
- Optionally creates a knowledge graph from a built corpus index for GraphRAG
- Creates RAG profiles using either `CRAG` or `GraphRAG`
- Optionally defines a counterpart persona
- Creates a negotiation scenario
- Creates a simulation for a user using the corpus index, the negotiation scenario, 

### Teacher

- Uploads raw documents (pdfs only). They are stored locally under /raw_docs_store
- Defines a corpus from uploaded documents
- Creates a negotiation scenario
- Review completed negotiations

### Student

- Selects negotiations, and participates in them


## TODOs:

- Move developing to WSL.
- Refactor god files.
- For completeness implement the BM25 retriever, even though it is not appropriate for the nature of the project.
- Decouple chunking from indexing, keep complete pipeline as a feature.
- Expand prompt guard module.
- Expand LLM provides coverage, only OpenAI and Ollama supported at the moment.
- Implement HippoRAG2 knowledge graphs (Unix-Linux only support).
- Abstract RAG strategies: CRAG and GraphRAG cohabitate in a disjointed manner, a 3rd RAG option would further complicate things. Need abstraction for isolation and reusability.
- Refactor project folder architecture to vertical slicing.
