import { useRef, useState, type FormEvent } from "react";

import type { LLMSelection } from "@/api/types";
import { LlmModelSelector } from "@/components/llm/LlmModelSelector";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { useEmbeddingModelsQuery } from "@/features/corpusIndices/corpusIndexQueries";
import { useLlmModelCatalogQuery } from "@/features/llmModels/llmModelQueries";

import {
  makeCragConfiguration,
  makeGraphRagConfiguration,
  type RagEvalConfigurationInput,
  type RagEvalFormErrors,
  type RagEvalLlmSelection,
} from "./ragEvaluationTypes";
import {
  normalizeRagEvalConfiguration,
  validateRagEvalConfiguration,
} from "./ragEvaluationValidation";

type ChunkingConfiguration = RagEvalConfigurationInput["chunking"];
type RagConfiguration = RagEvalConfigurationInput["rag"];
type ChunkingStrategy = ChunkingConfiguration["strategy"];
type RagStrategy = RagConfiguration["strategy"];

const commonRoles = [
  "document_grader",
  "query_rewriter",
  "answer_generator",
  "hallucination_grader",
  "answer_grader",
  "fallback_generator",
] as const;

const roleLabels: Record<(typeof commonRoles)[number], string> = {
  document_grader: "Document grader",
  query_rewriter: "Query rewriter",
  answer_generator: "Answer generator",
  hallucination_grader: "Hallucination grader",
  answer_grader: "Answer grader",
  fallback_generator: "Fallback generator",
};

const recursiveDefaults = {
  chunk_size: 1000,
  chunk_overlap: 200,
  separators: ["\n\n", "\n", " ", ""],
};

const semanticDefaults = {
  breakpoint_threshold_type: "percentile",
  breakpoint_threshold_amount: 90,
  buffer_size: 1,
};

export function RagEvaluationForm({
  initialValue,
  submitLabel,
  onSubmit,
  onCancel,
  onSubmissionStateChange,
  pending = false,
}: {
  initialValue?: RagEvalConfigurationInput;
  submitLabel: string;
  onSubmit: (value: RagEvalConfigurationInput) => void | Promise<void>;
  onCancel?: () => void;
  onSubmissionStateChange?: (inFlight: boolean) => void;
  pending?: boolean;
}) {
  const [configuration, setConfiguration] = useState<RagEvalConfigurationInput>(() =>
    structuredClone(initialValue ?? makeCragConfiguration()),
  );
  const [sharedDefault, setSharedDefault] = useState<RagEvalLlmSelection>(() => ({
    ...configuration.rag.document_grader,
  }));
  const [advancedOverridesOpen, setAdvancedOverridesOpen] = useState(false);
  const [errors, setErrors] = useState<RagEvalFormErrors>({});
  const [submissionInFlight, setSubmissionInFlight] = useState(false);
  const submissionInFlightRef = useRef(false);

  const embeddingModels = useEmbeddingModelsQuery();
  const llmCatalog = useLlmModelCatalogQuery();

  function updateConfiguration(update: (next: RagEvalConfigurationInput) => void) {
    setConfiguration((current) => {
      const next = structuredClone(current);
      update(next);
      return next;
    });
  }

  function updateSharedDefault(selection: LLMSelection) {
    const nextSelection = { ...selection };
    setSharedDefault(nextSelection);
    updateConfiguration((next) => {
      for (const role of commonRoles) {
        next.rag[role] = { ...nextSelection };
      }
      next.metrics.ragas_judge = { ...nextSelection };
      if (next.rag.strategy === "graphrag") {
        next.rag.extraction_llm = { ...nextSelection };
      }
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || submissionInFlightRef.current) {
      return;
    }
    const normalized = normalizeRagEvalConfiguration(configuration);
    const nextErrors = validateRagEvalConfiguration(normalized, {
      embeddingModelNames: embeddingModels.data
        ? new Set(embeddingModels.data.map((model) => model.name))
        : undefined,
      llmCatalog: llmCatalog.data,
    });
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      if (Object.keys(nextErrors).some((path) => isAdvancedLlmPath(path))) {
        setAdvancedOverridesOpen(true);
      }
      return;
    }
    submissionInFlightRef.current = true;
    setSubmissionInFlight(true);
    onSubmissionStateChange?.(true);
    void submitConfiguration(normalized);
  }

  async function submitConfiguration(normalized: RagEvalConfigurationInput) {
    try {
      await onSubmit(normalized);
    } finally {
      submissionInFlightRef.current = false;
      setSubmissionInFlight(false);
      onSubmissionStateChange?.(false);
    }
  }

  function changeChunkingStrategy(strategy: ChunkingStrategy) {
    updateConfiguration((next) => {
      next.chunking = chunkingForStrategy(next.chunking, strategy);
    });
  }

  function changeRagStrategy(strategy: RagStrategy) {
    updateConfiguration((next) => {
      next.rag = ragForStrategy(next.rag, strategy, sharedDefault);
    });
  }

  function updateCommonRole(
    role: (typeof commonRoles)[number],
    selection: LLMSelection,
  ) {
    updateConfiguration((next) => {
      next.rag[role] = { ...selection };
    });
  }

  const retrievalLimit = configuration.rag.strategy === "crag"
    ? configuration.rag.top_n
    : configuration.rag.evidence_limit;
  const controlsPending = pending || submissionInFlight;

  return (
    <form className="grid gap-6" noValidate onSubmit={handleSubmit}>
      <Field label="Name" error={errors.name}>
        <Input
          value={configuration.name}
          onChange={(event) => updateConfiguration((next) => {
            next.name = event.target.value;
          })}
        />
      </Field>

      <fieldset className="grid gap-4 rounded-xl border border-slate-200 p-4">
        <legend className="px-1 text-base font-semibold text-slate-900">Chunking</legend>
        <Field label="Chunking strategy">
          <Select
            value={configuration.chunking.strategy}
            onChange={(event) => changeChunkingStrategy(event.target.value as ChunkingStrategy)}
          >
            <option value="recursive">Recursive</option>
            <option value="semantic">Semantic</option>
            <option value="hybrid">Hybrid</option>
          </Select>
        </Field>

        {configuration.chunking.strategy === "recursive" ||
        configuration.chunking.strategy === "hybrid" ? (
          <div className="grid gap-4 md:grid-cols-2">
            <NumberField
              label="Chunk size"
              value={configuration.chunking.chunk_size}
              path="chunking.chunk_size"
              errors={errors}
              min={100}
              max={8000}
              onChange={(value) => updateConfiguration((next) => {
                if (next.chunking.strategy === "recursive" || next.chunking.strategy === "hybrid") {
                  next.chunking.chunk_size = value;
                }
              })}
            />
            <NumberField
              label="Chunk overlap"
              value={configuration.chunking.chunk_overlap}
              path="chunking.chunk_overlap"
              errors={errors}
              min={0}
              max={2000}
              onChange={(value) => updateConfiguration((next) => {
                if (next.chunking.strategy === "recursive" || next.chunking.strategy === "hybrid") {
                  next.chunking.chunk_overlap = value;
                }
              })}
            />
            <Field
              label="Separators"
              hint="One separator per line. Use \\n and \\n\\n for newline separators."
              error={errors["chunking.separators"]}
              className="md:col-span-2"
            >
              <Textarea
                aria-label="Separators"
                value={separatorsToText(configuration.chunking.separators ?? [])}
                onChange={(event) => {
                  const separators = textToSeparators(event.target.value);
                  updateConfiguration((next) => {
                    if (
                      next.chunking.strategy === "recursive" ||
                      next.chunking.strategy === "hybrid"
                    ) {
                      next.chunking.separators = separators;
                    }
                  });
                }}
              />
            </Field>
          </div>
        ) : null}

        {configuration.chunking.strategy === "semantic" ||
        configuration.chunking.strategy === "hybrid" ? (
          <div className="grid gap-4 md:grid-cols-3">
            <Field
              label="Breakpoint threshold type"
              error={errors["chunking.breakpoint_threshold_type"]}
            >
              <Input
                value={configuration.chunking.breakpoint_threshold_type}
                onChange={(event) => updateConfiguration((next) => {
                  if (next.chunking.strategy === "semantic" || next.chunking.strategy === "hybrid") {
                    next.chunking.breakpoint_threshold_type = event.target.value;
                  }
                })}
              />
            </Field>
            <NumberField
              label="Breakpoint threshold amount"
              value={configuration.chunking.breakpoint_threshold_amount}
              path="chunking.breakpoint_threshold_amount"
              errors={errors}
              min={1}
              onChange={(value) => updateConfiguration((next) => {
                if (next.chunking.strategy === "semantic" || next.chunking.strategy === "hybrid") {
                  next.chunking.breakpoint_threshold_amount = value;
                }
              })}
            />
            <NumberField
              label="Buffer size"
              value={configuration.chunking.buffer_size}
              path="chunking.buffer_size"
              errors={errors}
              min={0}
              onChange={(value) => updateConfiguration((next) => {
                if (next.chunking.strategy === "semantic" || next.chunking.strategy === "hybrid") {
                  next.chunking.buffer_size = value;
                }
              })}
            />
          </div>
        ) : null}
      </fieldset>

      <fieldset className="grid gap-4 rounded-xl border border-slate-200 p-4">
        <legend className="px-1 text-base font-semibold text-slate-900">Retrieval</legend>
        <Field label="RAG strategy">
          <Select
            value={configuration.rag.strategy}
            onChange={(event) => changeRagStrategy(event.target.value as RagStrategy)}
          >
            <option value="crag">CRAG</option>
            <option value="graphrag">GraphRAG</option>
          </Select>
        </Field>

        {configuration.rag.strategy === "crag" ? (
          <div className="grid gap-4 md:grid-cols-2">
            <EmbeddingModelField
              label="Retrieval embedding model"
              value={configuration.rag.retrieval_embedding_model}
              error={errors["rag.retrieval_embedding_model"]}
              models={embeddingModels.data ?? []}
              onChange={(value) => updateConfiguration((next) => {
                if (next.rag.strategy === "crag") {
                  next.rag.retrieval_embedding_model = value;
                }
              })}
            />
            <NumberField
              label="Top K"
              value={configuration.rag.top_k}
              path="rag.top_k"
              errors={errors}
              min={1}
              max={20}
              onChange={(value) => updateConfiguration((next) => {
                if (next.rag.strategy === "crag") {
                  next.rag.top_k = value;
                  if (next.rag.reranker === "none") {
                    next.rag.top_n = value;
                  }
                }
              })}
            />
            <Field label="Reranker" error={errors["rag.reranker"]}>
              <Select
                value={configuration.rag.reranker}
                onChange={(event) => updateConfiguration((next) => {
                  if (next.rag.strategy === "crag") {
                    next.rag.reranker = event.target.value;
                    if (next.rag.reranker === "none") {
                      next.rag.top_n = next.rag.top_k;
                    }
                  }
                })}
              >
                <option value="cross_encoder">Cross encoder</option>
                <option value="cohere">Cohere</option>
                <option value="none">None</option>
              </Select>
            </Field>
            <NumberField
              label="Top N"
              value={configuration.rag.top_n}
              path="rag.top_n"
              errors={errors}
              min={1}
              max={20}
              disabled={configuration.rag.reranker === "none"}
              onChange={(value) => updateConfiguration((next) => {
                if (next.rag.strategy === "crag" && next.rag.reranker !== "none") {
                  next.rag.top_n = value;
                }
              })}
            />
            <NumberField
              label="Rewrite limit"
              value={configuration.rag.rewrite_limit}
              path="rag.rewrite_limit"
              errors={errors}
              min={0}
              max={10}
              onChange={(value) => updateConfiguration((next) => {
                if (next.rag.strategy === "crag") {
                  next.rag.rewrite_limit = value;
                }
              })}
            />
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            <EmbeddingModelField
              label="Graph embedding model"
              value={configuration.rag.graph_embedding_model}
              error={errors["rag.graph_embedding_model"]}
              models={embeddingModels.data ?? []}
              onChange={(value) => updateConfiguration((next) => {
                if (next.rag.strategy === "graphrag") {
                  next.rag.graph_embedding_model = value;
                }
              })}
            />
            <NumberField
              label="Max paths per chunk"
              value={configuration.rag.max_paths_per_chunk}
              path="rag.max_paths_per_chunk"
              errors={errors}
              min={1}
              max={100}
              onChange={(value) => updateConfiguration((next) => {
                if (next.rag.strategy === "graphrag") {
                  next.rag.max_paths_per_chunk = value;
                }
              })}
            />
            <Field label="Retrieval mode" error={errors["rag.retrieval_mode"]}>
              <Select
                value={configuration.rag.retrieval_mode}
                onChange={(event) => updateConfiguration((next) => {
                  if (next.rag.strategy === "graphrag") {
                    next.rag.retrieval_mode = event.target.value as typeof next.rag.retrieval_mode;
                  }
                })}
              >
                <option value="semantic">Semantic</option>
                <option value="cypher">Cypher</option>
                <option value="hybrid">Hybrid</option>
              </Select>
            </Field>
            <NumberField
              label="Evidence limit"
              value={configuration.rag.evidence_limit}
              path="rag.evidence_limit"
              errors={errors}
              min={1}
              max={30}
              onChange={(value) => updateConfiguration((next) => {
                if (next.rag.strategy === "graphrag") {
                  next.rag.evidence_limit = value;
                }
              })}
            />
            <NumberField
              label="Traversal depth"
              value={configuration.rag.traversal_depth}
              path="rag.traversal_depth"
              errors={errors}
              min={1}
              max={5}
              onChange={(value) => updateConfiguration((next) => {
                if (next.rag.strategy === "graphrag") {
                  next.rag.traversal_depth = value;
                }
              })}
            />
            <NumberField
              label="RRF constant"
              value={configuration.rag.rrf_constant}
              path="rag.rrf_constant"
              errors={errors}
              min={1}
              max={200}
              onChange={(value) => updateConfiguration((next) => {
                if (next.rag.strategy === "graphrag") {
                  next.rag.rrf_constant = value;
                }
              })}
            />
          </div>
        )}
      </fieldset>

      <fieldset className="grid gap-4 rounded-xl border border-slate-200 p-4">
        <legend className="px-1 text-base font-semibold text-slate-900">Evaluation metrics</legend>
        <div className="grid gap-4 md:grid-cols-2">
          <NumberField
            label="Metric K"
            value={configuration.metrics.k}
            path="metrics.k"
            errors={errors}
            min={1}
            max={retrievalLimit}
            onChange={(value) => updateConfiguration((next) => {
              next.metrics.k = value;
            })}
          />
          <EmbeddingModelField
            label="Judge embedding model"
            value={configuration.metrics.judge_embedding_model}
            error={errors["metrics.judge_embedding_model"]}
            models={embeddingModels.data ?? []}
            onChange={(value) => updateConfiguration((next) => {
              next.metrics.judge_embedding_model = value;
            })}
          />
        </div>
      </fieldset>

      <fieldset className="grid gap-4 rounded-xl border border-slate-200 p-4">
        <legend className="px-1 text-base font-semibold text-slate-900">Language models</legend>
        <LlmModelSelector
          label="Default LLM provider"
          modelLabel="Default LLM model"
          catalog={llmCatalog.data}
          selection={sharedDefault as LLMSelection}
          onChange={updateSharedDefault}
          disabled={llmCatalog.isLoading}
          metadataMode="error-only"
          variant="plain"
          className="md:grid-cols-2"
        />
        <Button
          type="button"
          variant="secondary"
          onClick={() => setAdvancedOverridesOpen((open) => !open)}
        >
          {advancedOverridesOpen
            ? "Hide advanced LLM overrides"
            : "Show advanced LLM overrides"}
        </Button>

        {advancedOverridesOpen ? (
          <div
            className="grid gap-4 md:grid-cols-2"
            data-testid="advanced-llm-overrides"
          >
            {commonRoles.map((role) => (
              <OverrideSelector
                key={role}
                label={roleLabels[role]}
                selection={configuration.rag[role]}
                catalog={llmCatalog.data}
                disabled={llmCatalog.isLoading}
                providerError={errors[`rag.${role}.provider`]}
                modelError={errors[`rag.${role}.model`]}
                onChange={(selection) => updateCommonRole(role, selection)}
              />
            ))}
            <OverrideSelector
              label="RAGAS judge"
              selection={configuration.metrics.ragas_judge}
              catalog={llmCatalog.data}
              disabled={llmCatalog.isLoading}
              providerError={errors["metrics.ragas_judge.provider"]}
              modelError={errors["metrics.ragas_judge.model"]}
              onChange={(selection) => updateConfiguration((next) => {
                next.metrics.ragas_judge = { ...selection };
              })}
            />
            {configuration.rag.strategy === "graphrag" ? (
              <OverrideSelector
                label="Extraction"
                selection={configuration.rag.extraction_llm}
                catalog={llmCatalog.data}
                disabled={llmCatalog.isLoading}
                providerError={errors["rag.extraction_llm.provider"]}
                modelError={errors["rag.extraction_llm.model"]}
                onChange={(selection) => updateConfiguration((next) => {
                  if (next.rag.strategy === "graphrag") {
                    next.rag.extraction_llm = { ...selection };
                  }
                })}
              />
            ) : null}
          </div>
        ) : null}
      </fieldset>

      <div className="flex flex-wrap justify-end gap-3">
        {onCancel ? (
          <Button type="button" variant="secondary" disabled={controlsPending} onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
        <Button type="submit" disabled={controlsPending}>{submitLabel}</Button>
      </div>
    </form>
  );
}

function NumberField({
  label,
  value,
  path,
  errors,
  min,
  max,
  disabled = false,
  onChange,
}: {
  label: string;
  value: number;
  path: string;
  errors: RagEvalFormErrors;
  min: number;
  max?: number;
  disabled?: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <Field label={label} error={errors[path]}>
      <Input
        type="number"
        value={Number.isNaN(value) ? "" : value}
        min={min}
        max={max}
        step={1}
        disabled={disabled}
        onChange={(event) => onChange(numberFromInput(event.target.value))}
      />
    </Field>
  );
}

function EmbeddingModelField({
  label,
  value,
  error,
  models,
  onChange,
}: {
  label: string;
  value: string;
  error?: string;
  models: Array<{ name: string; display_name: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <Field label={label} error={error}>
      <Select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Select embedding model</option>
        {models.map((model) => (
          <option key={model.name} value={model.name}>{model.display_name}</option>
        ))}
      </Select>
    </Field>
  );
}

function OverrideSelector({
  label,
  selection,
  catalog,
  disabled,
  providerError,
  modelError,
  onChange,
}: {
  label: string;
  selection: RagEvalLlmSelection;
  catalog: Parameters<typeof LlmModelSelector>[0]["catalog"];
  disabled: boolean;
  providerError?: string;
  modelError?: string;
  onChange: (selection: LLMSelection) => void;
}) {
  return (
    <div className="grid content-start gap-1">
      <LlmModelSelector
        label={`${label} LLM provider`}
        modelLabel={`${label} LLM model`}
        catalog={catalog}
        selection={selection as LLMSelection}
        onChange={onChange}
        disabled={disabled}
        metadataMode="error-only"
        variant="plain"
        modelSelectProps={{ "data-llm-model": true }}
      />
      {providerError ? <p className="text-xs text-red-700">{providerError}</p> : null}
      {modelError ? <p className="text-xs text-red-700">{modelError}</p> : null}
    </div>
  );
}

function chunkingForStrategy(
  current: ChunkingConfiguration,
  strategy: ChunkingStrategy,
): ChunkingConfiguration {
  const recursive = current.strategy === "recursive" || current.strategy === "hybrid"
    ? {
        chunk_size: current.chunk_size,
        chunk_overlap: current.chunk_overlap,
        separators: [...(current.separators ?? recursiveDefaults.separators)],
      }
    : structuredClone(recursiveDefaults);
  const semantic = current.strategy === "semantic" || current.strategy === "hybrid"
    ? {
        breakpoint_threshold_type: current.breakpoint_threshold_type,
        breakpoint_threshold_amount: current.breakpoint_threshold_amount,
        buffer_size: current.buffer_size,
      }
    : { ...semanticDefaults };

  if (strategy === "recursive") {
    return { strategy, ...recursive };
  }
  if (strategy === "semantic") {
    return { strategy, ...semantic };
  }
  return { strategy, ...recursive, ...semantic };
}

function ragForStrategy(
  current: RagConfiguration,
  strategy: RagStrategy,
  sharedDefault: RagEvalLlmSelection,
): RagConfiguration {
  const next = structuredClone(
    strategy === "crag" ? makeCragConfiguration().rag : makeGraphRagConfiguration().rag,
  );
  for (const role of commonRoles) {
    next[role] = { ...current[role] };
  }
  if (next.strategy === "graphrag") {
    next.extraction_llm = { ...sharedDefault };
  }
  return next;
}

function separatorsToText(separators: string[]) {
  return separators
    .map((separator) => {
      if (separator === "\n\n") return "\\n\\n";
      if (separator === "\n") return "\\n";
      return separator;
    })
    .join("\n");
}

function textToSeparators(value: string) {
  return value.split("\n").map((separator) => {
    if (separator === "\\n\\n") return "\n\n";
    if (separator === "\\n") return "\n";
    return separator;
  });
}

function numberFromInput(value: string) {
  return value === "" ? Number.NaN : Number(value);
}

function isAdvancedLlmPath(path: string) {
  return path.includes(".provider") || path.includes(".model");
}
