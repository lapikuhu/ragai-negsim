import type { ApiComponents } from "@/api/types";

export type RagEvalConfigurationInput = ApiComponents["schemas"]["RagEvalConfigurationCreateRequest"];
export type RagEvalConfigurationUpdate = ApiComponents["schemas"]["RagEvalConfigurationUpdateRequest"];
export type RagEvalConfigurationRead = ApiComponents["schemas"]["RagEvalConfigurationRead"];
export type RagEvalRunRead = ApiComponents["schemas"]["RagEvalRunRead"];
export type RagEvalRunDetailRead = ApiComponents["schemas"]["RagEvalRunDetailRead"];
export type RagEvalQueryResultRead = ApiComponents["schemas"]["RagEvalQueryResultRead"];
export type RagEvalLlmSelection = ApiComponents["schemas"]["LLMSelection"];
export type RagEvalFormErrors = Record<string, string>;

const llm = (): RagEvalLlmSelection => ({ provider: "openai", model: "gpt-4o-mini" });
const responseLlms = () => ({
  document_grader: llm(),
  query_rewriter: llm(),
  answer_generator: llm(),
  hallucination_grader: llm(),
  answer_grader: llm(),
  fallback_generator: llm(),
});

export function makeCragConfiguration(): RagEvalConfigurationInput {
  return {
    name: "CRAG experiment",
    chunking: {
      strategy: "recursive",
      chunk_size: 1000,
      chunk_overlap: 200,
      separators: ["\n\n", "\n", " ", ""],
    },
    rag: {
      strategy: "crag",
      retrieval_embedding_model: "text-embedding-3-small",
      top_k: 4,
      reranker: "cross_encoder",
      top_n: 3,
      rewrite_limit: 2,
      ...responseLlms(),
    },
    metrics: {
      k: 3,
      ragas_judge: llm(),
      judge_embedding_model: "text-embedding-3-small",
    },
  };
}

export function makeGraphRagConfiguration(): RagEvalConfigurationInput {
  return {
    name: "GraphRAG experiment",
    chunking: {
      strategy: "recursive",
      chunk_size: 1000,
      chunk_overlap: 200,
      separators: ["\n\n", "\n", " ", ""],
    },
    rag: {
      strategy: "graphrag",
      graph_embedding_model: "text-embedding-3-small",
      extraction_llm: llm(),
      max_paths_per_chunk: 10,
      retrieval_mode: "semantic",
      evidence_limit: 6,
      traversal_depth: 2,
      rrf_constant: 60,
      ...responseLlms(),
    },
    metrics: {
      k: 3,
      ragas_judge: llm(),
      judge_embedding_model: "text-embedding-3-small",
    },
  };
}
