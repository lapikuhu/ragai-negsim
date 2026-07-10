import { useEffect, useMemo, useState } from "react";
import type { ApiComponents, VectorStoreRead } from "@/api/types";
import { getErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { useEmbeddingModelsQuery } from "@/features/corpusIndices/corpusIndexQueries";
import { parseJsonInput, stringifyJson } from "@/utils/format";

type VectorStoreBackend = ApiComponents["schemas"]["VectorStoreCreate"]["backend"];
type VectorStoreCreate = ApiComponents["schemas"]["VectorStoreCreate"];
type VectorStoreUpdate = ApiComponents["schemas"]["VectorStoreUpdate"];
type VectorStoreFormSubmit = VectorStoreCreate | VectorStoreUpdate;

type VectorStoreFormState = {
  name: string;
  backend: VectorStoreBackend;
  connectionUri: string;
  collectionName: string;
  tableName: string;
  path: string;
  embeddingModel: string;
  storeMetadata: string;
};

type VectorStoreFormProps = {
  initialValue?: Partial<VectorStoreRead>;
  submitLabel: string;
  submittingLabel: string;
  successMessage: string;
  onSubmit: (input: VectorStoreFormSubmit) => Promise<unknown>;
  onCancel?: () => void;
  onSuccess?: () => void;
  resetOnSuccess?: boolean;
};

const backendOptions: VectorStoreBackend[] = ["chroma", "faiss", "pgvector"];

export function VectorStoreForm({
  initialValue,
  submitLabel,
  submittingLabel,
  successMessage,
  onSubmit,
  onCancel,
  onSuccess,
  resetOnSuccess = false
}: VectorStoreFormProps) {
  const initialForm = useMemo(() => buildFormState(initialValue), [initialValue]);
  const models = useEmbeddingModelsQuery();
  const [form, setForm] = useState<VectorStoreFormState>(initialForm);
  const [message, setMessage] = useState<string | null>(null);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setForm(initialForm);
    setMessage(null);
    setMetadataError(null);
  }, [initialForm]);

  const backendHint = getBackendHint(form.backend);
  const isEditMode = Boolean(initialValue?.id);
  const selectedEmbeddingModel = (models.data ?? []).find((model) => model.name === form.embeddingModel) ?? null;
  const embeddingModelHint = selectedEmbeddingModel
    ? `Dimensions: ${selectedEmbeddingModel.dimensionality}`
    : "Select the embedding model used to size this vector store.";
  const storedDimensionsHint = initialValue?.embedding_dimensions
    ? `Dimensions: ${initialValue.embedding_dimensions}`
    : "Dimensions not set. This store cannot be used for new indexing jobs until dimensions are set.";

  return (
    <form
      className="grid gap-3"
      onSubmit={async (event) => {
        event.preventDefault();
        setMessage(null);

        let storeMetadata: Record<string, unknown>;
        try {
          storeMetadata = parseMetadataInput(form.storeMetadata);
          setMetadataError(null);
        } catch (error) {
          setMetadataError(error instanceof Error ? error.message : "Store metadata must be valid JSON.");
          return;
        }

        setIsSubmitting(true);
        try {
          const payload = {
            name: form.name.trim(),
            backend: form.backend,
            connection_uri: toNullable(form.connectionUri),
            collection_name: toNullable(form.collectionName),
            table_name: toNullable(form.tableName),
            path: toNullable(form.path),
            store_metadata: storeMetadata
          };
          await onSubmit(
            isEditMode
              ? payload
              : {
                  ...payload,
                  embedding_model: form.embeddingModel
                }
          );
          setMessage(successMessage);
          if (resetOnSuccess) {
            setForm(buildFormState());
          }
          onSuccess?.();
        } catch (error) {
          setMessage(getErrorMessage(error, "Unable to save vector store"));
        } finally {
          setIsSubmitting(false);
        }
      }}
    >
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Name" className="content-start">
          <Input
            value={form.name}
            onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            required
          />
        </Field>
        {isEditMode ? (
          <Field label="Vector dimensions" hint={storedDimensionsHint}>
            <Input value={initialValue?.embedding_dimensions?.toString() ?? "Not set"} disabled readOnly />
          </Field>
        ) : (
          <Field label="Embedding model" hint={embeddingModelHint} className="content-start">
            <Select
              value={form.embeddingModel}
              onChange={(event) => setForm((current) => ({ ...current, embeddingModel: event.target.value }))}
              disabled={models.isLoading}
              required
            >
              <option value="">Select model</option>
              {(models.data ?? []).map((model) => (
                <option key={model.name} value={model.name}>
                  {model.display_name}
                </option>
              ))}
            </Select>
          </Field>
        )}
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Backend" hint={backendHint.summary}>
          <Select
            value={form.backend}
            onChange={(event) =>
              setForm((current) => ({ ...current, backend: event.target.value as VectorStoreBackend }))
            }
            required
          >
            {backendOptions.map((backend) => (
              <option key={backend} value={backend}>
                {backend}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Connection URI" hint={backendHint.connectionUri}>
          <Input
            value={form.connectionUri}
            onChange={(event) => setForm((current) => ({ ...current, connectionUri: event.target.value }))}
            placeholder={form.backend === "pgvector" ? "postgresql+psycopg://..." : undefined}
          />
        </Field>
        <Field label="Path" hint={backendHint.path}>
          <Input
            value={form.path}
            onChange={(event) => setForm((current) => ({ ...current, path: event.target.value }))}
            placeholder={form.backend === "faiss" ? "./stores/catalog.faiss" : "./chroma_db"}
          />
        </Field>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Collection name" hint={backendHint.collectionName}>
          <Input
            value={form.collectionName}
            onChange={(event) => setForm((current) => ({ ...current, collectionName: event.target.value }))}
          />
        </Field>
        <Field label="Table name" hint={backendHint.tableName}>
          <Input
            value={form.tableName}
            onChange={(event) => setForm((current) => ({ ...current, tableName: event.target.value }))}
          />
        </Field>
      </div>

      <Field
        label="Store metadata JSON"
        hint="Optional JSON object stored with the vector store. Leave blank to store an empty object."
        error={metadataError ?? undefined}
      >
        <Textarea
          className="min-h-40 font-mono text-sm"
          value={form.storeMetadata}
          onChange={(event) => setForm((current) => ({ ...current, storeMetadata: event.target.value }))}
          placeholder="{}"
        />
      </Field>

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={isSubmitting || (!isEditMode && !form.embeddingModel)}>
          {isSubmitting ? submittingLabel : submitLabel}
        </Button>
        {onCancel ? (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
        {message ? <span className="text-sm text-slate-600">{message}</span> : null}
      </div>
    </form>
  );
}

function buildFormState(initialValue?: Partial<VectorStoreRead>): VectorStoreFormState {
  return {
    name: initialValue?.name ?? "",
    backend: initialValue?.backend ?? "chroma",
    connectionUri: initialValue?.connection_uri ?? "",
    collectionName: initialValue?.collection_name ?? "",
    tableName: initialValue?.table_name ?? "",
    path: initialValue?.path ?? "",
    embeddingModel: "",
    storeMetadata: stringifyJson(initialValue?.store_metadata ?? {})
  };
}

function parseMetadataInput(value: string) {
  const parsed = parseJsonInput<unknown>(value, {});
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Store metadata must be a JSON object.");
  }
  return parsed as Record<string, unknown>;
}

function toNullable(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function getBackendHint(backend: VectorStoreBackend) {
  if (backend === "pgvector") {
    return {
      summary: "Typically uses a database connection URI and table name.",
      connectionUri: "Usually required for pgvector-backed stores.",
      path: "Usually unused for pgvector.",
      collectionName: "Optional unless your backend setup uses named collections.",
      tableName: "Typically the target table for pgvector storage."
    };
  }

  if (backend === "faiss") {
    return {
      summary: "Typically uses a filesystem path.",
      connectionUri: "Usually unused for faiss.",
      path: "Typically the local file or directory path.",
      collectionName: "Usually unused for faiss.",
      tableName: "Usually unused for faiss."
    };
  }

  return {
    summary: "Typically uses a local path and may use a collection name.",
    connectionUri: "Optional depending on how chroma is configured.",
    path: "Often the local chroma storage directory.",
    collectionName: "Optional collection identifier for chroma.",
    tableName: "Usually unused for chroma."
  };
}
