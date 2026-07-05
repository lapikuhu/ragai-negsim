# Simulation and learner domain

This repository's core product is a negotiation simulation engine. A simulation combines scenario context, counterpart persona data, prompts, retrieval context, learner settings, coaching, and evaluation into a single turn-based workflow.

## Business purpose
The simulation domain exists so learners can practice negotiation with feedback. The system does not just generate chat responses; it structures the exchange into explicit stages:
- classify learner intent
- generate counterpart replies
- produce coach advice
- evaluate the current turn or the completed negotiation
- record evidence and token usage for later review

Recent commits show this area expanding quickly, especially around the learner assistant and evidence/source capture. That makes this page the canonical home for understanding simulation behavior.

## Main backend entrypoints
- `app/web/routes/simulations_route.py` exposes create/list/update/turn/review endpoints.
- `app/services/simulations_service.py` orchestrates simulation lifecycle and negotiation graph execution.
- `app/services/simulation_learner_service.py` handles the learner assistant feature.

## Core concepts
### Simulation lifecycle
A simulation can be created from the available scenario, corpus, prompt, persona, and retrieval configuration. It then moves through statuses such as active, paused, completed, cancelled, or failed. The service layer treats some statuses as terminal and others as runnable.

### Negotiation graph
The negotiation graph in `app/airag/chains/negotiation/negotiation.py` is the main orchestration structure. It defines the parent negotiation state, wraps agent subgraphs, and routes through deterministic branches such as intent classification and final evaluation.

### Agent subgraphs
The parent negotiation flow delegates work to dedicated agent graphs:
- counterpart negotiation
- coach advice
- evaluator scoring
- intent classification
- user proxy negotiation
- learner assistant

The `app/airag/chains/agents/context_projections.py` module is important because it strips the parent state down to the exact fields each subgraph should see.

### Learner assistant
The learner assistant is a separate feature from the counterpart. It is exposed through the simulation service and can answer learner-facing questions during a simulation. It can use:
- CRAG retrieval
- GraphRAG retrieval
- negotiation summarization
- Tavily web search

The assistant is designed to provide answers without leaking private prompt or reasoning internals. Its prompt is assembled from learner-safe context only.

### Evidence ledger
The evidence ledger records retrieval sources, pipeline steps, quality checks, model metadata, and token usage. This is what lets later review pages and tests inspect why the model answered the way it did.

## Data flow for a turn
1. The frontend sends a turn or learner question to the simulations API.
2. The service loads the simulation and runtime context.
3. A negotiation subgraph is invoked with a projected state.
4. Retrieval may be performed through CRAG or GraphRAG, depending on the simulation's configuration.
5. The coach/evaluator/learner output is normalized and stored.
6. Evidence ledger records are written so the turn can be reviewed later.

## Files worth reading first
- `app/airag/chains/negotiation/negotiation.py`
- `app/airag/chains/agents/context_projections.py`
- `app/airag/chains/agents/learner/learner_agent.py`
- `app/airag/chains/agents/learner/learner_helpers.py`
- `app/airag/observability/evidence_ledger.py`
- `app/services/simulations_service.py`
- `app/services/simulation_learner_service.py`
- `app/web/routes/simulations_route.py`

## Change guidance
When editing this domain, check these first:
- If you change what the learner can see, update the projection helpers and the learner prompt together.
- If you change turn state shape, update the negotiation graph, service serialization, and tests in tandem.
- If you change evidence source behavior, verify both CRAG and GraphRAG source-card tests.
- If you change completion or review logic, inspect the review endpoints and evaluation tests.

## Relevant tests
The most useful tests here include:
- `tests/test_simulations_service.py`
- `tests/test_simulation_learner_service.py`
- `tests/test_negotiation_graph.py`
- `tests/test_evidence_ledger.py`
- `tests/test_crag_grounding.py`
- `tests/test_graphrag_retrieval.py`
- `tests/test_simulations_evaluations_api.py`

## Source pointers
- `app/services/simulations_service.py`
- `app/services/simulation_learner_service.py`
- `app/airag/chains/negotiation/negotiation.py`
- `app/airag/chains/agents/context_projections.py`
- `app/airag/observability/evidence_ledger.py`
- `app/web/routes/simulations_route.py`
