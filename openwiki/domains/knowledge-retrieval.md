# Knowledge and retrieval domain

This repository grounds simulations in uploaded course or domain material. The retrieval stack currently supports both CRAG-style corrective retrieval and GraphRAG-style knowledge-graph retrieval.

## What this domain does
The knowledge/retrieval domain is responsible for:
- uploading raw PDF documents
- linking documents to corpora
- parsing, chunking, and indexing document content
- preparing vector and graph retrieval backends
- attaching source evidence to model outputs

This is a central business domain because the simulator is meant to be grounded in course or scenario material, not just generated from conversation history.

## Main backend entrypoints
- `app/web/routes/raw_documents_route.py`
- `app/web/routes/document_chunks_route.py`
- `app/web/routes/corpus_route.py`
- `app/web/routes/corpus_indices_route.py`
- `app/web/routes/rag_profiles_route.py`
- `app/web/routes/knowledge_graph_indices_route.py`
- `app/web/routes/knowledge_graph_build_jobs_route.py`
- `app/web/routes/vector_stores_route.py`

## Document flow
1. A raw document is uploaded through the raw-documents API.
2. The document can be associated with one or more corpora at creation time.
3. Ingestion parses the document into chunks.
4. Chunking profiles control how chunks are produced.
5. Chunk records can be inspected separately in the document chunks UI/API.
6. Later retrieval uses those chunks as evidence for simulation and learner responses.

The raw document route now exposes associated corpora in its detail response, and recent changes also surface bibliographic metadata (`document_title`, `document_author`, `document_year`) through the document APIs and source cards. Raw document uploads reject non-PDF files, verify the PDF signature, enforce configured size limits, and reject duplicate stored filenames before persisting metadata. Source verification also updates `source_status` as the on-disk file changes, so `available`, `missing`, `changed`, `unverified`, and `error` are now meaningful states in the document lifecycle. That makes document metadata and upload validation first-class parts of the retrieval domain, not just upload details.

Recent CRAG changes add a prompt-injection guard at the retrieval node: unsafe queries are blocked before vector lookup, the pipeline step is recorded as blocked, and no documents are returned. Successful retrieval and rerank paths still attach sources to the evidence ledger.

Simulation and learner-question flows now also run the shared prompt guard before invoking the negotiation graph or learner agent, which means retrieval-domain changes can affect both uploaded-document grounding and service-layer request rejection.

## CRAG and GraphRAG
The README and recent git history show two retrieval strategies:

### CRAG
CRAG is corrective retrieval over the configured vector store. It retrieves candidate chunks, reranks them, grades relevance, can rewrite the query if evidence is weak, and produces a grounded answer.

### GraphRAG
GraphRAG uses a knowledge graph backed by Neo4j. It can retrieve evidence through semantic graph search, validated text-to-Cypher, or a hybrid ranking strategy.

Both strategies now return sources. That source capture is important because the evidence ledger and learner assistant rely on it to explain where an answer came from.

## Evidence ledger and source cards
`app/airag/observability/evidence_ledger.py` defines how source cards are built and stored. Important details:
- Only a safe subset of metadata is copied into source cards.
- Source cards can be built from `Document` objects.
- The ledger can extract sources from nested CRAG/GraphRAG structures.
- Ledger records include pipeline steps, quality checks, model metadata, token usage, and output summaries.

This module is the canonical place to inspect when retrieval output changes shape.

## Prompt guards and runnable invocation
`app/airag/observability/llm_usage.py` now includes `guarded_invoke_with_config`, which normalizes a payload to text and runs it through `return_guarded_query` before invoking the runnable. The helper currently relies on the new scaffold in `app/airag/prompt_guard/prompt_guard.py`, where prompt-injection patterns are implemented and PII detection remains a placeholder.

At the moment this is a front-door validation layer rather than a full policy engine: the tests only confirm that safe payloads pass through and prompt-injection strings are blocked before the runnable is called. Future changes here should check both the guard module and the usage-tracking tests.

## Related components
- `app/services/raw_documents_service.py` handles upload and association behavior.
- `app/services/ingestion_service.py` and `app/services/chunking_service.py` handle parse/chunk workflows.
- `app/services/document_chunks_service.py` and `app/repositories/document_chunks_repo.py` support chunk browsing.
- `app/services/corpus_service.py` and `app/services/corpus_indices_service.py` connect corpora to indices.
- `app/services/rag_profiles_service.py` models retrieval profile settings.
- `app/services/knowledge_graph_builds_service.py` orchestrates graph build jobs, tracks progress, and guards against stale chunk snapshots while a build is running.
- `app/airag/knowledge_graph/scoped_schema_store.py` keeps Neo4j schema refresh scoped to the active logical graph generation.
- `app/models/knowledge_graph_build_jobs.py` and `app/schemas/knowledge_graph_build_jobs_schemas.py` define the build-job progress fields now used by the UI.

## Knowledge graph build jobs
Knowledge graph builds now carry richer progress metadata so the UI can show a live in-progress state rather than just queued or completed jobs. Build jobs track the number of documents and chunks queued for a graph, the current raw document being processed, the current document label, and the node and relationship counts persisted into Neo4j.

The build service snapshots the exact chunk IDs at queue time and refuses to continue if the corpus index changes before execution. That makes the build safer for long-running jobs and explains why the Knowledge Graphs page polls both graphs and build jobs while a job is active.

The new migration `migrations/versions/d5e8f1a2b3c4_add_knowledge_graph_build_progress.py` adds the corresponding database columns. If you change build-job state again, update the model, schema, service, repository, migration, and the page together.

## What to watch out for
- A retrieval change usually affects simulation grounding, learner answers, evidence ledger contents, and tests all at once.
- Neo4j graph retrieval expects the relevant database configuration and APOC support.
- Source metadata is intentionally filtered; avoid leaking extra metadata into public responses without checking the evidence ledger rules.

## Relevant tests
- `tests/test_raw_documents_service.py`
- `tests/test_document_chunks_service.py`
- `tests/test_crag_grounding.py`
- `tests/test_crag_evidence_ledger.py`
- `tests/test_graphrag_retrieval.py`
- `tests/test_graphrag_profile_binding.py`
- `tests/test_knowledge_graph_builds_service.py`
- `tests/test_knowledge_graph_domain.py`

## Source pointers
- `app/airag/observability/evidence_ledger.py`
- `app/services/raw_documents_service.py`
- `app/services/ingestion_service.py`
- `app/services/chunking_service.py`
- `app/services/document_chunks_service.py`
- `app/services/corpus_service.py`
- `app/services/rag_profiles_service.py`
