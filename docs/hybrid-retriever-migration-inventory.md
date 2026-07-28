# Hybrid retriever migration inventory

This inventory records the production touchpoints present at the start of
hybrid retriever migration plan 1. It is intentionally descriptive: plan 1
does not construct a BM25 runtime or change dense retrieval behavior.

## Configuration contract

Reusable CRAG profiles contain retrieval policy, not concrete runtime artifact
identities:

- `bm25_weight` is a float from `0.0` through `1.0`, inclusive.
- `dense_k`, `bm25_k`, and `final_top_k` are integers from `1` through `20`,
  inclusive, and each defaults to `4`.
- `dense_k` and `bm25_k` are candidate limits for their respective retrievers.
- `final_top_k` is the maximum fused result count before reranking and must be
  less than or equal to `max(dense_k, bm25_k)`.
- `bm25_weight == 0.0` means dense-only retrieval.
- `bm25_weight == 1.0` means BM25-only retrieval.
- A weight strictly between `0.0` and `1.0` means hybrid retrieval.

The existing reranker contract remains downstream of retrieval:
`top_n <= final_top_k`, and the `none` reranker normalizes `top_n` to
`final_top_k`.

Concrete corpus-index and BM25-artifact IDs belong on a simulation/runtime
binding. They must not be stored in reusable `RagProfile.config`; otherwise a
profile could not be safely reused across corpus-index generations.

## LangChain `EnsembleRetriever`

All production-tree references are currently in
`app/airag/retrieval/retrievers.py`:

- line 3 imports `EnsembleRetriever`.
- `make_hybrid_retriever()` uses it as its return annotation and constructs it
  from dense and BM25 retrievers.
- `make_hybrid_retriever()` is imported and invoked only by
  `app/airag/chains/agents/agents_scratch.py`, an import-time scratch module,
  not the simulation runtime.

Later runtime work must not assume this legacy helper already satisfies the
new independent candidate limits and `final_top_k` contract.

## Dense factory entry points

- `app/airag/retrieval/retrievers.py:make_dense_retriever()` is the shared
  dense retriever adapter. Its signature is
  `(vector_store, k=4, metadata_filter=None)`.
- `app/airag/retrieval/retrievers.py:make_hybrid_retriever()` calls the dense
  factory internally with its legacy shared `k`.
- `app/services/simulations_service.py` imports `make_dense_retriever()` and
  calls it in `_build_retrieval_graph()`.
- `_instantiate_vector_store_for_index()` in that service dispatches to
  `instantiate_chroma_vector_store()`, `load_faiss_vector_store()`, or
  `instantiate_pgvector_store()`, defined in
  `app/airag/vector_stores/vector_stores.py`.
- `app/core/dependencies.py:get_runtime_vector_store()` (line 1456) separately
  dispatches Chroma at line 1472 and FAISS at line 1479 for the generic
  retrieval dependency.

Plan 1 does not change any of these signatures or implementations.

## `top_k` and related K usages

CRAG simulation retrieval:

- `app/services/simulations_service.py:_build_retrieval_graph()` currently
  reads legacy `rag_profile.config["top_k"]` (default `4`) and passes it to
  `make_dense_retriever()`. A later plan must replace this with mode-aware
  dense/BM25 candidate construction and final truncation.

CRAG reranking (downstream, not a retrieval-candidate limit):

- `app/airag/pipeline_factory.py:build_response_pipeline()` maps profile
  `top_n` to `rerank_top_k`.
- `app/airag/chains/crag/crag.py:make_crag()` validates and forwards
  `rerank_top_k`.
- `app/airag/chains/crag/crag_nodes.py:make_crag_rerank_node()` passes its
  `top_k` to the selected reranker and records it in evidence detail.
- `app/airag/reranking/reranking.py` uses `top_k` in cross-encoder, no-rerank,
  and Cohere reranker implementations.

Other retrieval domains that are not migrated by these CRAG runtime plans:

- `app/schemas/rag_eval_schemas.py:CragRagEvalConfig.top_k` and
  `app/airag/evaluation/rag_eval_runtime.py` define the isolated, dense-only
  RAG-evaluation candidate limit. RAG evaluation remains dense-only.
- `app/airag/retrieval/retrievers.py:make_graph_retriever()` passes `k` as
  LlamaIndex `similarity_top_k`; this is graph retrieval, not CRAG hybrid
  retrieval.
- `app/core/dependencies.py:RetrievalOptions.rerank_top_k` and
  `get_retrieval_options()` belong to the generic retrieval dependency, not
  the simulation profile contract.

## Negotiation graph cache

- `app/services/simulations_service.py:NEGOTIATION_GRAPH_CACHE` owns cached
  compiled negotiation graphs.
- `_graph_cache_key()` builds the tuple. It includes corpus-index identity and
  generation-related vector metadata, vector-store identity, serialized
  profile config, GraphRAG identity/generation, prompts, and LLM selection.
- `_get_negotiation_graph_for_simulation()` is the only production cache-key
  constructor call site and performs the cache read/write.
- `clear_negotiation_graph_cache_for_knowledge_graph()` removes GraphRAG
  entries using `GRAPH_CACHE_KNOWLEDGE_GRAPH_ID_INDEX`.

When BM25 artifacts are runtime-bound, later plans must add the binding's
artifact identity/version to `_graph_cache_key()`. Relying only on reusable
profile config would retain stale or wrong-corpus BM25 runtimes indirectly
through `NEGOTIATION_GRAPH_CACHE`.
