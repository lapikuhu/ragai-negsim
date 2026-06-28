# Backend Gaps

Date: 2026-06-28

This file records frontend needs that are not fully supported by the current backend contract.

Last checked against:

- `app/main.py`
- `app/web/routes/corpus_route.py`
- `app/web/routes/corpus_indices_route.py`
- `app/web/routes/indexing_jobs_route.py`
- `app/web/routes/simulations_route.py`
- `app/web/routes/users_route.py`
- `app/schemas/corpus_schemas.py`
- `app/schemas/corpus_indices_schemas.py`
- `app/schemas/embeddings_schemas.py`
- `app/schemas/indexing_jobs_schemas.py`
- `app/schemas/simulations_schemas.py`
- `app/schemas/users_schemas.py`

## Resolved since 2026-06-05

### Role metadata endpoint

Status: resolved with an authenticated admin endpoint.

Endpoint:

- `GET /users/roles`

Response shape:

```json
[
  { "id": 1, "name": "admin" },
  { "id": 2, "name": "student" },
  { "id": 3, "name": "teacher" }
]
```

Notes:

- `app.web.routes.users_route.list_roles` exposes the endpoint as `GET /users/roles` with `response_model=list[RoleRead]`.
- The endpoint requires `AdminDep`, so it supports admin user-management forms rather than unauthenticated role discovery.

### Indexing job monitor

Status: resolved for the newer indexing job workflow; still separate from the legacy corpus embed-job route.

Endpoints:

- `POST /indexing-jobs/`
- `GET /indexing-jobs/`
- `GET /indexing-jobs/active`
- `GET /indexing-jobs/{job_id}`
- `POST /indexing-jobs/{job_id}/cancel`

Response shape for `GET /indexing-jobs/{job_id}`:

```json
{
  "id": 12,
  "corpus_id": 1,
  "chunking_profile_id": 2,
  "vector_store_id": 3,
  "embedding_model": "mini-l6-v2",
  "requested_index_name": "Course corpus index",
  "requested_vector_namespace": null,
  "status": "queued",
  "stage": "validating",
  "cancel_requested": false,
  "current_raw_document_id": null,
  "current_document_name": null,
  "total_documents": 0,
  "processed_documents": 0,
  "chunks_created": 0,
  "chunks_indexed": 0,
  "queued_at": "2026-06-28T12:00:00Z",
  "started_at": null,
  "completed_at": null,
  "candidate_corpus_index_id": null,
  "replaced_corpus_index_id": null,
  "failure_detail": null,
  "warnings": []
}
```

Notes:

- `app.web.routes.indexing_jobs_route` exposes list, detail, active-job, and cancel routes with `IndexingJobQueued` and `IndexingJobDetail` response models.
- Progress is represented by document and chunk counters: `total_documents`, `processed_documents`, `chunks_created`, and `chunks_indexed`.
- The older `POST /corpora/{corpus_id}/chunking-profiles/{profile_id}/vector-stores/{vector_store_id}/embed-jobs` route still returns `CorpusEmbeddingBuildQueued` and points `poll_url` to `/corpus-indices/{corpus_index_id}`. That route does not expose a job-id based monitor by itself.

## Remaining gaps

### 1. Corpus detail endpoint

Screen or action:

- corpus detail page with authoritative single-record fetch

Proposed endpoint:

- `GET /corpora/{corpus_id}`

Request shape:

- path parameter `corpus_id: int`

Response shape:

```json
{
  "id": 1,
  "name": "Course corpus",
  "description": "Optional description",
  "created_by_user_id": 1,
  "created_by_username": "admin",
  "last_edit_by_user_id": 1,
  "last_edit_by_username": "admin",
  "created_at": "2026-06-28T12:00:00Z",
  "raw_document_ids": [1, 2],
  "corpus_index_ids": [3],
  "simulation_ids": [4]
}
```

Why existing endpoints are insufficient:

- `app.web.routes.corpus_route` currently exposes `POST /corpora/`, `GET /corpora/`, and corpus ingestion, chunking, and embedding actions, but no `GET /corpora/{corpus_id}` route.
- `CorpusReadWithIds` and repository helpers already exist for related IDs, but the route and service layer do not expose them for a single corpus detail read.

### 2. Standalone evaluations API

Screen or action:

- evaluation list and evaluation detail pages

Proposed endpoint:

- `GET /evaluations/`
- `GET /evaluations/{evaluation_id}`

Request shape:

- optional filters such as `simulation_id`, `teacher_id`, `status`

Response shape:

```json
{
  "id": 9,
  "simulation_id": 4,
  "score": 0.78,
  "reasoning": "The learner anchored early but missed trade-off framing.",
  "detected_risks": ["premature concession"],
  "next_best_action": "Ask a value-discovery question",
  "created_at": "2026-06-28T12:00:00Z"
}
```

Why existing endpoints are insufficient:

- `app.web.routes.simulations_route` exposes simulation review flows through `GET /simulations/reviews`, `GET /simulations/completed`, and `POST/PATCH/DELETE /simulations/{simulation_id}/review`.
- `SimulationEvaluationListResponse` is a simulation list shape, not a standalone evaluation resource. It does not expose a stable evaluation ID, score, reasoning, detected risks, or next-best-action contract.
- Runtime turn responses can include `final_evaluation`, but that remains nested in simulation turn output rather than queryable as its own API resource.

### 3. Settings endpoints

Screen or action:

- editable app settings and user preferences

Proposed endpoint:

- `GET /settings`
- `PATCH /settings`
- `GET /users/me/preferences`
- `PATCH /users/me/preferences`

Request shape:

- standard JSON settings payload

Response shape:

```json
{
  "default_embedding_model": "mini-l6-v2",
  "default_chunking_profile_id": 1,
  "ui_preferences": {
    "dense_tables": true
  }
}
```

Why existing endpoints are insufficient:

- The backend exposes domain configuration resources such as embedding models, chunking profiles, RAG profiles, prompts, LLM catalogs, vector stores, and user password changes.
- No registered route currently exposes general app settings or per-user UI preferences.

### 4. Dashboard summary endpoint

Screen or action:

- dashboard with a single efficient summary fetch

Proposed endpoint:

- `GET /dashboard`

Request shape:

- none, or optional role-aware filters

Response shape:

```json
{
  "recent_simulations": [],
  "recent_documents": [],
  "recent_sessions": [],
  "alerts": [],
  "quick_actions": []
}
```

Why existing endpoints are insufficient:

- `app/main.py` does not register a dashboard router, and the route scan does not show a `GET /dashboard` endpoint.
- The dashboard must still fan out to list endpoints and handle role-dependent authorization behavior client-side.
