import clsx from "clsx";
import type { LLMModelCatalogResponse, LLMProvider, LLMSelection } from "@/api/types";
import { Field, Select } from "@/components/ui/Field";

type MetadataMode = "gpu-and-error" | "error-only" | "none";
type SelectorVariant = "panel" | "plain";

export function getDefaultCatalogModel(
  catalog: LLMModelCatalogResponse | undefined,
  provider: LLMProvider,
) {
  return catalog?.providers.find((entry) => entry.provider === provider)?.models[0]?.name ?? null;
}

export function LlmModelSelector({
  label,
  modelLabel = "Model",
  catalog,
  selection,
  onChange,
  disabled = false,
  metadataMode = "gpu-and-error",
  variant = "panel",
  className,
}: {
  label: string;
  modelLabel?: string;
  catalog?: LLMModelCatalogResponse;
  selection: LLMSelection;
  onChange: (selection: LLMSelection) => void;
  disabled?: boolean;
  metadataMode?: MetadataMode;
  variant?: SelectorVariant;
  className?: string;
}) {
  const providerCatalog = catalog?.providers.find((provider) => provider.provider === selection.provider);
  const models = providerCatalog?.models ?? [];
  const metadata = buildProviderMetadata(catalog, providerCatalog?.error, metadataMode, selection.provider);

  return (
    <div
      className={clsx(
        "grid gap-2",
        variant === "panel" ? "rounded-lg border border-slate-200 bg-slate-50 p-3" : null,
        className,
      )}
    >
      <Field label={label}>
        <Select
          value={selection.provider}
          disabled={disabled}
          onChange={(event) => {
            const provider = event.target.value as LLMProvider;
            onChange({ provider, model: getDefaultCatalogModel(catalog, provider) ?? "" });
          }}
        >
          <option value="openai">OpenAI</option>
          <option value="ollama">Ollama</option>
        </Select>
      </Field>
      <Field label={modelLabel}>
        <Select
          value={selection.model}
          disabled={disabled || !models.length}
          onChange={(event) => onChange({ ...selection, model: event.target.value })}
        >
          <option value="">{models.length ? "Select model" : "No models available"}</option>
          {models.map((model) => (
            <option key={model.name} value={model.name}>
              {model.name}
              {selection.provider === "ollama" && typeof model.size_gib === "number" ? ` (${model.size_gib} GiB)` : ""}
            </option>
          ))}
        </Select>
      </Field>
      {metadata ? <p className="text-xs text-slate-500">{metadata}</p> : null}
    </div>
  );
}

function buildProviderMetadata(
  catalog: LLMModelCatalogResponse | undefined,
  providerError: string | null | undefined,
  mode: MetadataMode,
  provider: LLMProvider,
) {
  if (provider !== "ollama" || mode === "none") {
    return null;
  }

  if (mode === "error-only") {
    return providerError ?? null;
  }

  const memory = typeof catalog?.gpu_memory_gib === "number" ? `${catalog.gpu_memory_gib} GiB` : "unknown";
  return `GPU memory: ${memory}${providerError ? `; ${providerError}` : ""}`;
}
