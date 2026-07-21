import type { LLMModelCatalogResponse } from "@/api/types";

import type {
  RagEvalConfigurationInput,
  RagEvalFormErrors,
  RagEvalLlmSelection,
} from "./ragEvaluationTypes";

export type RagEvalValidationContext = {
  embeddingModelNames?: Set<string>;
  llmCatalog?: LLMModelCatalogResponse;
};

const responseSelectionKeys = [
  "document_grader",
  "query_rewriter",
  "answer_generator",
  "hallucination_grader",
  "answer_grader",
  "fallback_generator",
] as const;

const errorMessage = "Enter a valid value.";

function addError(errors: RagEvalFormErrors, path: string, message = errorMessage) {
  errors[path] = message;
}

function isIntegerInRange(value: number, minimum: number, maximum?: number) {
  return Number.isInteger(value) && value >= minimum && (maximum === undefined || value <= maximum);
}

function validateEmbeddingModel(
  value: string,
  path: string,
  errors: RagEvalFormErrors,
  modelNames?: Set<string>,
) {
  const model = value.trim();
  if (!model) {
    addError(errors, path, "Select an embedding model.");
  } else if (modelNames && !modelNames.has(model)) {
    addError(errors, path, "Select an available embedding model.");
  }
}

function validateLlmSelection(
  selection: RagEvalLlmSelection,
  path: string,
  errors: RagEvalFormErrors,
  catalog?: LLMModelCatalogResponse,
) {
  const provider = selection.provider.trim();
  const model = selection.model.trim();

  if (provider !== "openai" && provider !== "ollama") {
    addError(errors, `${path}.provider`, "Select OpenAI or Ollama.");
  }
  if (!model) {
    addError(errors, `${path}.model`, "Select a model.");
    return;
  }

  if (!catalog || (provider !== "openai" && provider !== "ollama")) {
    return;
  }

  const providerCatalog = catalog.providers.find((item) => item.provider === provider);
  if (!providerCatalog?.models.some((item) => item.name === model)) {
    addError(errors, `${path}.model`, "Select a model available for this provider.");
  }
}

function trimLlmSelection(selection: RagEvalLlmSelection) {
  selection.provider = selection.provider.trim();
  selection.model = selection.model.trim();
}

export function normalizeRagEvalConfiguration(
  input: RagEvalConfigurationInput,
): RagEvalConfigurationInput {
  const normalized = structuredClone(input);
  normalized.name = normalized.name.trim();

  if (
    normalized.chunking.strategy === "semantic" ||
    normalized.chunking.strategy === "hybrid"
  ) {
    normalized.chunking.breakpoint_threshold_type =
      normalized.chunking.breakpoint_threshold_type.trim();
  }

  for (const key of responseSelectionKeys) {
    trimLlmSelection(normalized.rag[key]);
  }
  trimLlmSelection(normalized.metrics.ragas_judge);
  normalized.metrics.judge_embedding_model = normalized.metrics.judge_embedding_model.trim();

  if (normalized.rag.strategy === "crag") {
    normalized.rag.retrieval_embedding_model = normalized.rag.retrieval_embedding_model.trim();
    if (normalized.rag.reranker === "none") {
      normalized.rag.top_n = normalized.rag.top_k;
    }
  } else {
    normalized.rag.graph_embedding_model = normalized.rag.graph_embedding_model.trim();
    trimLlmSelection(normalized.rag.extraction_llm);
  }

  return normalized;
}

export function validateRagEvalConfiguration(
  input: RagEvalConfigurationInput,
  context: RagEvalValidationContext = {},
): RagEvalFormErrors {
  const normalized = normalizeRagEvalConfiguration(input);
  const errors: RagEvalFormErrors = {};

  if (normalized.name.length < 3) {
    addError(errors, "name", "Name must contain at least three characters.");
  }

  const chunking = normalized.chunking;
  if (chunking.strategy === "recursive" || chunking.strategy === "hybrid") {
    if (!isIntegerInRange(chunking.chunk_size, 100, 8000)) {
      addError(errors, "chunking.chunk_size");
    }
    if (
      !isIntegerInRange(chunking.chunk_overlap, 0, 2000) ||
      chunking.chunk_overlap >= chunking.chunk_size
    ) {
      addError(errors, "chunking.chunk_overlap");
    }
    if (
      !Array.isArray(chunking.separators) ||
      !chunking.separators.every((separator) => typeof separator === "string")
    ) {
      addError(errors, "chunking.separators", "Enter separators as a list of strings.");
    }
  }
  if (chunking.strategy === "semantic" || chunking.strategy === "hybrid") {
    if (!chunking.breakpoint_threshold_type) {
      addError(errors, "chunking.breakpoint_threshold_type");
    }
    if (!isIntegerInRange(chunking.breakpoint_threshold_amount, 1)) {
      addError(errors, "chunking.breakpoint_threshold_amount");
    }
    if (!isIntegerInRange(chunking.buffer_size, 0)) {
      addError(errors, "chunking.buffer_size");
    }
  }

  for (const key of responseSelectionKeys) {
    validateLlmSelection(
      normalized.rag[key],
      `rag.${key}`,
      errors,
      context.llmCatalog,
    );
  }
  validateLlmSelection(
    normalized.metrics.ragas_judge,
    "metrics.ragas_judge",
    errors,
    context.llmCatalog,
  );
  validateEmbeddingModel(
    normalized.metrics.judge_embedding_model,
    "metrics.judge_embedding_model",
    errors,
    context.embeddingModelNames,
  );

  if (normalized.rag.strategy === "crag") {
    const rag = normalized.rag;
    validateEmbeddingModel(
      rag.retrieval_embedding_model,
      "rag.retrieval_embedding_model",
      errors,
      context.embeddingModelNames,
    );
    if (!isIntegerInRange(rag.top_k, 1, 20)) {
      addError(errors, "rag.top_k");
    }
    if (!(["cross_encoder", "cohere", "none"] as string[]).includes(rag.reranker)) {
      addError(errors, "rag.reranker");
    }
    if (!isIntegerInRange(rag.top_n, 1, 20) || rag.top_n > rag.top_k) {
      addError(errors, "rag.top_n");
    }
    if (!isIntegerInRange(rag.rewrite_limit, 0, 10)) {
      addError(errors, "rag.rewrite_limit");
    }
  } else {
    const rag = normalized.rag;
    validateEmbeddingModel(
      rag.graph_embedding_model,
      "rag.graph_embedding_model",
      errors,
      context.embeddingModelNames,
    );
    validateLlmSelection(
      rag.extraction_llm,
      "rag.extraction_llm",
      errors,
      context.llmCatalog,
    );
    if (!isIntegerInRange(rag.max_paths_per_chunk, 1, 100)) {
      addError(errors, "rag.max_paths_per_chunk");
    }
    if (!(["semantic", "cypher", "hybrid"] as string[]).includes(rag.retrieval_mode)) {
      addError(errors, "rag.retrieval_mode");
    }
    if (!isIntegerInRange(rag.evidence_limit, 1, 30)) {
      addError(errors, "rag.evidence_limit");
    }
    if (!isIntegerInRange(rag.traversal_depth, 1, 5)) {
      addError(errors, "rag.traversal_depth");
    }
    if (!isIntegerInRange(rag.rrf_constant, 1, 200)) {
      addError(errors, "rag.rrf_constant");
    }
  }

  const retrievalLimit = normalized.rag.strategy === "crag"
    ? normalized.rag.top_n
    : normalized.rag.evidence_limit;
  if (!isIntegerInRange(normalized.metrics.k, 1) || normalized.metrics.k > retrievalLimit) {
    addError(errors, "metrics.k");
  }

  return errors;
}
