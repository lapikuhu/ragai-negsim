import type { ApiComponents } from "@/api/types";

type GeneratedRagEvalConfigurationInput = ApiComponents["schemas"]["RagEvalConfigurationCreateRequest"];
export type CragEvaluationConfiguration = Omit<
  ApiComponents["schemas"]["CragEvaluationConfiguration"],
  | "bm25_weight"
  | "dense_k"
  | "bm25_k"
  | "final_top_k"
  | "reranker"
  | "top_n"
  | "max_rewrite_attempts"
> & {
  bm25_weight: number;
  dense_k: number;
  bm25_k: number;
  final_top_k: number;
  reranker: string;
  top_n: number;
  max_rewrite_attempts: number;
};
export type RagEvalConfigurationInput = Omit<GeneratedRagEvalConfigurationInput, "rag"> & {
  rag: CragEvaluationConfiguration | ApiComponents["schemas"]["GraphRagEvaluationConfiguration"];
};
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
      bm25_weight: 0,
      dense_k: 4,
      bm25_k: 4,
      final_top_k: 4,
      reranker: "cross_encoder",
      top_n: 3,
      max_rewrite_attempts: 2,
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
