import type { RagProfileDefinitionRead } from "@/api/types";
import { Field, Input, Select } from "@/components/ui/Field";

export type RagDefinitionFieldValues = Record<string, string>;
type CragRetrievalValues = {
  bm25_weight?: string | number;
  dense_k?: string | number;
  bm25_k?: string | number;
  final_top_k?: string | number;
};

export function RagProfileDefinitionFields({
  definition,
  fieldValues,
  onChange,
  errors = {},
  disabled = false,
}: {
  definition: RagProfileDefinitionRead;
  fieldValues: RagDefinitionFieldValues;
  onChange: (fieldName: string, value: string) => void;
  errors?: Record<string, string>;
  disabled?: boolean;
}) {
  const mode = definition.strategy === "crag" ? getCragRetrievalMode(fieldValues) : null;
  return (
    <div className="grid gap-3">
      {mode ? (
        <span className="w-fit rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
          {mode === "dense" ? "Dense retrieval" : mode === "bm25" ? "BM25 retrieval" : "Hybrid retrieval"}
        </span>
      ) : null}
      <div className="grid gap-3 md:grid-cols-2">
        {definition.fields.map((field) => {
          const modeDisabled =
            (field.name === "bm25_k" && mode === "dense") ||
            (field.name === "dense_k" && mode === "bm25") ||
            (field.name === "top_n" && fieldValues.reranker === "none");
          return (
            <Field
              key={field.name}
              label={field.label}
              hint={field.help_text ?? undefined}
              error={errors[field.name]}
            >
              {field.kind === "enum" ? (
                <Select
                  value={fieldValues[field.name] ?? String(field.default)}
                  disabled={disabled || modeDisabled}
                  required={field.required}
                  onChange={(event) => onChange(field.name, event.target.value)}
                >
                  {field.options.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </Select>
              ) : (
                <Input
                  type="number"
                  min={field.minimum ?? undefined}
                  max={field.maximum ?? undefined}
                  step={field.kind === "float" ? 0.1 : 1}
                  disabled={disabled || modeDisabled}
                  required={field.required}
                  value={fieldValues[field.name] ?? String(field.default)}
                  onChange={(event) => onChange(field.name, event.target.value)}
                />
              )}
            </Field>
          );
        })}
      </div>
    </div>
  );
}

export function buildFieldValues(
  definition: RagProfileDefinitionRead,
  config?: Record<string, unknown>,
): RagDefinitionFieldValues {
  return Object.fromEntries(
    definition.fields.map((field) => [
      field.name,
      String(config?.[field.name] ?? field.default ?? ""),
    ]),
  );
}

export function packDefinitionFieldValues(
  definition: RagProfileDefinitionRead,
  fieldValues: RagDefinitionFieldValues,
) {
  return Object.fromEntries(
    definition.fields.map((field) => {
      const value = fieldValues[field.name] ?? "";
      return [field.name, field.kind === "enum" ? value : Number(value)];
    }),
  );
}

export function getCragRetrievalMode(values: CragRetrievalValues) {
  const weight = Number(values.bm25_weight ?? 0);
  if (weight === 0) return "dense" as const;
  if (weight === 1) return "bm25" as const;
  return "hybrid" as const;
}

export function getCragEffectiveCapacity(values: CragRetrievalValues) {
  const mode = getCragRetrievalMode(values);
  const denseK = Number(values.dense_k ?? 0);
  const bm25K = Number(values.bm25_k ?? 0);
  const finalTopK = Number(values.final_top_k ?? 0);
  if (mode === "dense") return Math.min(denseK, finalTopK);
  if (mode === "bm25") return Math.min(bm25K, finalTopK);
  return finalTopK;
}

export function updateDefinitionFieldValues(
  definition: RagProfileDefinitionRead,
  current: RagDefinitionFieldValues,
  fieldName: string,
  value: string,
) {
  const next = { ...current, [fieldName]: value };
  if (definition.strategy === "crag" && next.reranker === "none") {
    next.top_n = String(getCragEffectiveCapacity(next));
  }
  return next;
}

export function validateCragFieldValues(values: Record<string, string | number>) {
  const errors: Record<string, string> = {};
  const denseK = Number(values.dense_k ?? 0);
  const bm25K = Number(values.bm25_k ?? 0);
  const finalTopK = Number(values.final_top_k ?? 0);
  if (finalTopK > Math.max(denseK, bm25K)) {
    errors.final_top_k = "Final retrieval results cannot exceed the larger candidate limit.";
  }
  if (Number(values.top_n ?? 0) > getCragEffectiveCapacity(values)) {
    errors.top_n = "Reranked documents cannot exceed the effective retrieval capacity.";
  }
  return errors;
}
