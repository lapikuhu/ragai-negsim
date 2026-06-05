# Backend Gaps

Date: 2026-06-05

This file records frontend needs that are not fully supported by the current backend contract.

## 1. Corpus detail endpoint

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
  "last_edit_by_user_id": 1,
  "created_at": "2026-06-05T12:00:00Z",
  "raw_document_ids": [1, 2],
  "corpus_index_ids": [3],
  "simulation_ids": [4]
}
```

Why existing endpoints are insufficient:

- the frontend currently has to infer corpus detail from `GET /corpora/`, which is brittle and prevents direct cacheable detail reads.

## 2. Queued embedding job status

Screen or action:

- monitoring a queued embedding build after `POST /corpora/{corpus_id}/chunking-profiles/{profile_id}/vector-stores/{vector_store_id}/embed-jobs`

Proposed endpoint:

- `GET /embed-jobs/{job_id}`
- or `GET /corpus-indices/{index_id}/jobs`

Request shape:

- path parameter `job_id: int` or `index_id: int`

Response shape:

```json
{
  "job_id": 12,
  "status": "queued",
  "corpus_index_id": 3,
  "started_at": null,
  "completed_at": null,
  "error": null,
  "progress": {
    "processed_chunks": 0,
    "total_chunks": 200
  }
}
```

Why existing endpoints are insufficient:

- the current `202 Accepted` response is enough to confirm queueing but not enough to drive a real job monitor.

## 3. Standalone evaluations API

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
  "created_at": "2026-06-05T12:00:00Z"
}
```

Why existing endpoints are insufficient:

- evaluation-like information is only partially available through simulation review fields and latest turn outputs.

## 4. Settings endpoints

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

- the current API exposes domain configuration objects but not general app or user settings resources.

## 5. Dashboard summary endpoint

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

- the dashboard currently fans out to multiple list endpoints and has to tolerate role-based 401/403 behavior client-side.

## 6. Role metadata endpoint

Screen or action:

- user creation form with readable role choices instead of raw role IDs

Proposed endpoint:

- `GET /roles`

Request shape:

- none

Response shape:

```json
[
  { "id": 1, "name": "admin" },
  { "id": 2, "name": "student" },
  { "id": 3, "name": "teacher" }
]
```

Why existing endpoints are insufficient:

- `UserCreate` currently requires `role_ids`, but the frontend has no schema-backed way to discover those IDs dynamically.
