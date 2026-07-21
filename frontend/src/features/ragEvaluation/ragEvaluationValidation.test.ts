import { describe, expect, it } from "vitest";

import type { LLMModelCatalogResponse } from "@/api/types";
import {
  makeCragConfiguration,
  makeGraphRagConfiguration,
  type RagEvalConfigurationInput,
  type RagEvalLlmSelection,
} from "./ragEvaluationTypes";
import {
  normalizeRagEvalConfiguration,
  validateRagEvalConfiguration,
} from "./ragEvaluationValidation";

type CragInput = RagEvalConfigurationInput & {
  rag: Extract<RagEvalConfigurationInput["rag"], { strategy: "crag" }>;
};
type GraphRagInput = RagEvalConfigurationInput & {
  rag: Extract<RagEvalConfigurationInput["rag"], { strategy: "graphrag" }>;
};

const llmCatalog: LLMModelCatalogResponse = {
  providers: [
    { provider: "openai", models: [{ name: "gpt-4o-mini" }, { name: "gpt-4.1-mini" }] },
    { provider: "ollama", models: [{ name: "llama3.2" }] },
  ],
};

const validationContext = {
  embeddingModelNames: new Set(["text-embedding-3-small"]),
  llmCatalog,
};

function cragConfiguration(): CragInput {
  return makeCragConfiguration() as CragInput;
}

function graphRagConfiguration(): GraphRagInput {
  return makeGraphRagConfiguration() as GraphRagInput;
}

function expectInvalid(
  input: RagEvalConfigurationInput,
  path: string,
  context = validationContext,
) {
  expect(validateRagEvalConfiguration(input, context)).toHaveProperty(path);
}

const responseSelectionKeys = [
  "document_grader",
  "query_rewriter",
  "answer_generator",
  "hallucination_grader",
  "answer_grader",
  "fallback_generator",
] as const;

function allSelections(input: RagEvalConfigurationInput): RagEvalLlmSelection[] {
  const selections = responseSelectionKeys.map((key) => input.rag[key]);
  selections.push(input.metrics.ragas_judge);
  if (input.rag.strategy === "graphrag") {
    selections.push(input.rag.extraction_llm);
  }
  return selections;
}

describe("RAG evaluation configuration validation", () => {
  it("accepts valid CRAG and GraphRAG configurations", () => {
    expect(validateRagEvalConfiguration(makeCragConfiguration())).toEqual({});
    expect(validateRagEvalConfiguration(makeGraphRagConfiguration())).toEqual({});
  });

  it("normalizes without mutating and preserves the empty-string separator", () => {
    const input = graphRagConfiguration();
    input.name = "  Graph experiment  ";
    input.rag.graph_embedding_model = "  text-embedding-3-small  ";
    input.rag.extraction_llm = { provider: "  ollama  ", model: "  llama3.2  " };
    input.metrics.judge_embedding_model = "  text-embedding-3-small  ";
    input.metrics.ragas_judge = { provider: "  openai  ", model: "  gpt-4o-mini  " };
    input.rag.document_grader = { provider: "  openai  ", model: "  gpt-4.1-mini  " };
    const before = structuredClone(input);

    const normalized = normalizeRagEvalConfiguration(input);

    expect(normalized).not.toBe(input);
    expect(input).toEqual(before);
    expect(normalized.name).toBe("Graph experiment");
    expect(normalized.rag).toMatchObject({
      graph_embedding_model: "text-embedding-3-small",
      extraction_llm: { provider: "ollama", model: "llama3.2" },
      document_grader: { provider: "openai", model: "gpt-4.1-mini" },
    });
    expect(normalized.metrics).toMatchObject({
      judge_embedding_model: "text-embedding-3-small",
      ragas_judge: { provider: "openai", model: "gpt-4o-mini" },
    });
    expect(normalized.chunking.strategy).toBe("recursive");
    if (normalized.chunking.strategy === "recursive") {
      expect(normalized.chunking.separators).toEqual(["\n\n", "\n", " ", ""]);
    }
  });

  it("normalizes reranker none by copying top_k into top_n", () => {
    const input = cragConfiguration();
    input.rag.reranker = "none";
    input.rag.top_k = 7;
    input.rag.top_n = 2;
    expect(normalizeRagEvalConfiguration(input).rag).toMatchObject({
      reranker: "none",
      top_k: 7,
      top_n: 7,
    });
  });

  it("requires a trimmed name of at least three characters", () => {
    const input = makeCragConfiguration();
    input.name = "  ab  ";
    expectInvalid(input, "name");
  });

  it("requires all always-present LLM provider and model selections", () => {
    const selectionCases = [
      ...responseSelectionKeys.map((key) => ({
        path: `rag.${key}`,
        get: (input: CragInput) => input.rag[key],
      })),
      { path: "metrics.ragas_judge", get: (input: CragInput) => input.metrics.ragas_judge },
    ];

    for (const { path, get } of selectionCases) {
      const missingProvider = cragConfiguration();
      get(missingProvider).provider = "   ";
      expectInvalid(missingProvider, `${path}.provider`);

      const missingModel = cragConfiguration();
      get(missingModel).model = "   ";
      expectInvalid(missingModel, `${path}.model`);
    }
  });

  it("requires all eight GraphRAG LLM selections", () => {
    const input = graphRagConfiguration();
    input.rag.extraction_llm.model = "";
    expect(validateRagEvalConfiguration(input)).toHaveProperty("rag.extraction_llm.model");
  });

  it("enforces provider and provider-specific model catalog membership", () => {
    const unsupportedProvider = cragConfiguration();
    unsupportedProvider.rag.document_grader.provider = "anthropic";
    expectInvalid(unsupportedProvider, "rag.document_grader.provider");

    const wrongProvider = cragConfiguration();
    wrongProvider.rag.document_grader = { provider: "ollama", model: "gpt-4o-mini" };
    expectInvalid(wrongProvider, "rag.document_grader.model");
  });

  it("accepts valid OpenAI and Ollama selections from a loaded catalog", () => {
    const openAi = makeCragConfiguration();
    expect(validateRagEvalConfiguration(openAi, validationContext)).toEqual({});

    const ollama = makeGraphRagConfiguration();
    for (const selection of allSelections(ollama)) {
      selection.provider = "ollama";
      selection.model = "llama3.2";
    }
    expect(validateRagEvalConfiguration(ollama, validationContext)).toEqual({});
  });

  it("omits only catalog membership errors until catalogs load", () => {
    const input = cragConfiguration();
    input.rag.retrieval_embedding_model = "custom-embedding";
    input.metrics.judge_embedding_model = "custom-judge-embedding";
    input.rag.document_grader.model = "custom-chat-model";

    expect(validateRagEvalConfiguration(input)).toEqual({});
  });

  it("validates recursive and hybrid chunk size boundaries and integer values", () => {
    const cases = [
      { value: 99, strategy: "recursive" as const },
      { value: 8001, strategy: "recursive" as const },
      { value: 100.5, strategy: "recursive" as const },
      { value: 99, strategy: "hybrid" as const },
      { value: 8001, strategy: "hybrid" as const },
      { value: 100.5, strategy: "hybrid" as const },
    ];

    for (const testCase of cases) {
      const input = makeCragConfiguration();
      input.chunking = testCase.strategy === "recursive"
        ? { strategy: "recursive", chunk_size: testCase.value, chunk_overlap: 20, separators: [""] }
        : {
            strategy: "hybrid",
            chunk_size: testCase.value,
            chunk_overlap: 20,
            separators: [""],
            breakpoint_threshold_type: "percentile",
            breakpoint_threshold_amount: 90,
            buffer_size: 1,
          };
      expectInvalid(input, "chunking.chunk_size");
    }
  });

  it("validates recursive and hybrid overlap boundaries, integer values, and chunk size relation", () => {
    for (const strategy of ["recursive", "hybrid"] as const) {
      for (const overlap of [-1, 2001, 1.5, 1000]) {
        const input = makeCragConfiguration();
        input.chunking = strategy === "recursive"
          ? { strategy, chunk_size: 1000, chunk_overlap: overlap, separators: [""] }
          : {
              strategy,
              chunk_size: 1000,
              chunk_overlap: overlap,
              separators: [""],
              breakpoint_threshold_type: "percentile",
              breakpoint_threshold_amount: 90,
              buffer_size: 1,
            };
        expectInvalid(input, "chunking.chunk_overlap");
      }
    }
  });

  it("requires recursive and hybrid separators to be arrays of strings", () => {
    for (const strategy of ["recursive", "hybrid"] as const) {
      for (const separators of ["not-an-array", ["ok", 3]]) {
        const input = makeCragConfiguration();
        input.chunking = {
          strategy,
          chunk_size: 1000,
          chunk_overlap: 200,
          separators,
          ...(strategy === "hybrid"
            ? {
                breakpoint_threshold_type: "percentile",
                breakpoint_threshold_amount: 90,
                buffer_size: 1,
              }
            : {}),
        } as RagEvalConfigurationInput["chunking"];
        expectInvalid(input, "chunking.separators");
      }
    }
  });

  it("validates semantic and hybrid threshold and buffer boundaries", () => {
    for (const strategy of ["semantic", "hybrid"] as const) {
      const makeInput = () => {
        const input = makeCragConfiguration();
        input.chunking = {
          strategy,
          breakpoint_threshold_type: "percentile",
          breakpoint_threshold_amount: 90,
          buffer_size: 1,
          ...(strategy === "hybrid"
            ? { chunk_size: 1000, chunk_overlap: 200, separators: [""] }
            : {}),
        } as RagEvalConfigurationInput["chunking"];
        return input;
      };

      const missingType = makeInput();
      if (missingType.chunking.strategy === "recursive") {
        throw new Error("Expected semantic or hybrid chunking");
      }
      missingType.chunking.breakpoint_threshold_type = "   ";
      expectInvalid(missingType, "chunking.breakpoint_threshold_type");

      for (const amount of [0, 1.5]) {
        const input = makeInput();
        if (input.chunking.strategy === "recursive") {
          throw new Error("Expected semantic or hybrid chunking");
        }
        input.chunking.breakpoint_threshold_amount = amount;
        expectInvalid(input, "chunking.breakpoint_threshold_amount");
      }

      for (const bufferSize of [-1, 0.5]) {
        const input = makeInput();
        if (input.chunking.strategy === "recursive") {
          throw new Error("Expected semantic or hybrid chunking");
        }
        input.chunking.buffer_size = bufferSize;
        expectInvalid(input, "chunking.buffer_size");
      }
    }
  });

  it("validates CRAG embedding, reranker, and numeric boundaries", () => {
    const numericCases: Array<{
      field: "top_k" | "top_n" | "rewrite_limit";
      path: string;
      values: number[];
    }> = [
      { field: "top_k", path: "rag.top_k", values: [0, 21, 1.5] },
      { field: "top_n", path: "rag.top_n", values: [0, 21, 1.5] },
      { field: "rewrite_limit", path: "rag.rewrite_limit", values: [-1, 11, 0.5] },
    ];
    for (const { field, path, values } of numericCases) {
      for (const value of values) {
        const input = cragConfiguration();
        input.rag[field] = value;
        expectInvalid(input, path);
      }
    }

    const excessiveTopN = cragConfiguration();
    excessiveTopN.rag.top_k = 3;
    excessiveTopN.rag.top_n = 4;
    expectInvalid(excessiveTopN, "rag.top_n");

    const invalidReranker = cragConfiguration();
    invalidReranker.rag.reranker = "invalid";
    expectInvalid(invalidReranker, "rag.reranker");

    const emptyEmbedding = cragConfiguration();
    emptyEmbedding.rag.retrieval_embedding_model = "   ";
    expectInvalid(emptyEmbedding, "rag.retrieval_embedding_model");

    const unknownEmbedding = cragConfiguration();
    unknownEmbedding.rag.retrieval_embedding_model = "unknown";
    expectInvalid(unknownEmbedding, "rag.retrieval_embedding_model");
  });

  it("validates GraphRAG embedding, mode, and all numeric boundaries", () => {
    const numericCases: Array<{
      field: "max_paths_per_chunk" | "evidence_limit" | "traversal_depth" | "rrf_constant";
      path: string;
      values: number[];
    }> = [
      { field: "max_paths_per_chunk", path: "rag.max_paths_per_chunk", values: [0, 101, 1.5] },
      { field: "evidence_limit", path: "rag.evidence_limit", values: [0, 31, 1.5] },
      { field: "traversal_depth", path: "rag.traversal_depth", values: [0, 6, 1.5] },
      { field: "rrf_constant", path: "rag.rrf_constant", values: [0, 201, 1.5] },
    ];
    for (const { field, path, values } of numericCases) {
      for (const value of values) {
        const input = graphRagConfiguration();
        input.rag[field] = value;
        expectInvalid(input, path);
      }
    }

    const invalidMode = graphRagConfiguration();
    invalidMode.rag.retrieval_mode = "invalid" as GraphRagInput["rag"]["retrieval_mode"];
    expectInvalid(invalidMode, "rag.retrieval_mode");

    const emptyEmbedding = graphRagConfiguration();
    emptyEmbedding.rag.graph_embedding_model = "   ";
    expectInvalid(emptyEmbedding, "rag.graph_embedding_model");

    const unknownEmbedding = graphRagConfiguration();
    unknownEmbedding.rag.graph_embedding_model = "unknown";
    expectInvalid(unknownEmbedding, "rag.graph_embedding_model");
  });

  it("validates metrics k integer, minimum, and strategy-specific retrieval limit", () => {
    for (const value of [0, 1.5]) {
      const input = makeCragConfiguration();
      input.metrics.k = value;
      expectInvalid(input, "metrics.k");
    }

    const crag = cragConfiguration();
    crag.metrics.k = crag.rag.top_n + 1;
    expectInvalid(crag, "metrics.k");

    const graphRag = graphRagConfiguration();
    graphRag.metrics.k = graphRag.rag.evidence_limit + 1;
    expectInvalid(graphRag, "metrics.k");
  });

  it("validates the judge embedding model", () => {
    for (const model of ["   ", "unknown"] as const) {
      const input = makeCragConfiguration();
      input.metrics.judge_embedding_model = model;
      expectInvalid(input, "metrics.judge_embedding_model");
    }
  });
});
