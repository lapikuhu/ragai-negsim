# RAG Evaluation Production-Parity Design

## Goal

Make isolated CRAG RAG-evaluation runs support dense-only, BM25-only, and hybrid retrieval with the same validation, defaults, retrieval factories, and ranking provenance as production profiles.

## Architecture

The evaluation configuration keeps response-model selections at its existing top level.  It projects the seven CRAG retrieval controls into the production normalizer, then merges the normalized retrieval result with those response selections for the shared runtime response pipeline.  The inferred `bm25_weight` mode determines which run-scoped resources are created: FAISS for dense/hybrid, BM25 for BM25/hybrid, or both for hybrid.

Evaluation chunks are tagged, ordered, and assigned stable integer `document_chunk_id` values exactly once before either index is built.  Retrieval metadata (`dense_rank`, `bm25_rank`, and `fused_score`) travels through the canonical response pipeline to the safe persisted final-chunk API representation.

## Backend Contract

- CRAG controls are `bm25_weight`, `dense_k`, `bm25_k`, `final_top_k`, `reranker`, `top_n`, and `max_rewrite_attempts`.
- Production helpers `normalize_rag_profile_config` and `get_crag_retrieval_mode` are authoritative for validation, defaults, capacity, and mode selection.
- `retrieval_embedding_model` is required and resolved for dense/hybrid, forbidden for BM25-only, and omitted from normalized configurations and immutable snapshots for BM25-only.
- Index construction remains off the event-loop thread and preserves the current cancellation and cleanup guarantees.
- Resolved snapshots identify retrieval mode, active embedding identity when applicable, and dependency identities.
- GraphRAG evaluation behavior remains unchanged. No endpoint or database migration is introduced.

## Frontend Contract

The evaluation editor consumes `/rag-profiles/definitions` and shares a definition-driven field renderer and numeric coercion with the RAG Profiles editor. It infers retrieval mode immediately, shows the embedding selector only when required, clears it when switching to BM25-only, and blocks editing with a retryable error when definitions cannot load. Summaries show mode and effective capacity; run details show ranking provenance when supplied.

## Verification

Tests cover schema validation and immutable snapshots, all three runtime index modes, stable chunk IDs and hybrid metadata persistence, API persistence, frontend definition loading and mode transitions, generated schema, unit suites, frontend tests/build, and an OpenWiki correction removing the dense-only statement.

## Scope Decisions

The existing uncommitted docstring-only change in `app/airag/evaluation/rag_eval_runtime.py` is preserved unchanged. The database is assumed flushed before deployment, so no compatibility migration is needed.
