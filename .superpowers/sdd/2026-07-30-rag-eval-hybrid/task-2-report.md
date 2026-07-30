# Task 2 — Production-parity isolated CRAG adapters

## Contract

Implemented against schema contract commit `83fc3cb`. The scope is limited to
the evaluation runtime/engine and their focused unit tests; GraphRAG behavior,
endpoints, and migrations were not changed.

## RED

1. Replaced the dense-only adapter test with a parameterized dense/BM25/hybrid
   contract test. It verifies deterministic `document_chunk_id` assignment,
   factory arguments, construction selection, resolved mode/dependencies, and
   the absence of embedding/FAISS work for BM25-only mode.
2. Extended the full-pipeline final-context test with `dense_rank`,
   `bm25_rank`, and `fused_score`.
3. Ran the focused suite before implementation. The adapter test failed because
   the old implementation called `Store.as_retriever(...)` directly instead of
   using the production factory. The safe-metadata test also failed because the
   three hybrid rank fields were filtered out.

## GREEN

- Tagged chunks are copied once, in their prepared order, with integer IDs
  `1..n`; the resulting list is shared by FAISS and BM25 construction.
- CRAG mode is inferred with `get_crag_retrieval_mode`.
  - Dense: builds FAISS plus the dense factory only.
  - BM25: builds the BM25 factory only, without resolving an embedding model or
    importing/building FAISS.
  - Hybrid: builds both and joins them through `make_hybrid_retriever`.
- FAISS and BM25 construction run with `asyncio.to_thread`; the three
  production retriever factories receive the normalized candidate, fusion, and
  weight settings.
- Resolved metadata now records retrieval mode, active embedding identity (or
  `null` for BM25-only), and mode-relevant dependency versions.
- Final persisted chunks retain hybrid rank metadata through
  `EVALUATION_SAFE_METADATA`.
- Existing failure/cancellation and evaluator cleanup coverage remains in the
  focused runtime suite.

## Verification

```text
uv run ruff format ...                       # formatted 4 task files
uv run ruff check ...                        # passed
uv run pytest tests/unit/test_rag_eval_runtime_adapters.py \
  tests/unit/test_rag_eval_full_pipeline_runtime.py --maxfail=1 -q
16 passed in 29.90s
git diff --check                             # passed
```

## Concern

No known regression. CRAG still uses the pre-existing no-op resource cleanup:
the in-memory FAISS and BM25 runtime objects do not expose explicit close
operations, while cancellation and evaluator cleanup control flow are retained.
