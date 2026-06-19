import { useEffect, useState } from "react";
import { getErrorMessage } from "@/api/client";
import type {
  LLMModelCatalogResponse,
  LLMSelection,
  ScenarioAuthoringRead,
  ScenarioContextGenerateResponse,
  ScenarioRead
} from "@/api/types";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field, Input, Textarea } from "@/components/ui/Field";
import {
  useCreateScenarioMutation,
  useGenerateScenarioContextMutation,
  useScenarioAuthoringQuery,
  useScenariosQuery,
  useUpdateScenarioMutation
} from "@/features/scenarios/scenarioQueries";
import { useLlmModelCatalogQuery } from "@/features/llmModels/llmModelQueries";
import { LlmModelSelector, getDefaultCatalogModel } from "@/components/llm/LlmModelSelector";
import { formatDateTime, parseJsonInput, stringifyJson } from "@/utils/format";

type ScenarioFormState = {
  name: string;
  description: string;
  publicContext: string;
  sideAPrivateContext: string;
  sideBPrivateContext: string;
  llmSelection: LLMSelection;
  advancedOpen: boolean;
  generatedOnce: boolean;
};

const EMPTY_FORM: ScenarioFormState = {
  name: "",
  description: "",
  publicContext: "{}",
  sideAPrivateContext: "{}",
  sideBPrivateContext: "{}",
  llmSelection: { provider: "openai", model: "" },
  advancedOpen: false,
  generatedOnce: false
};

function applyGeneratedContext(
  form: ScenarioFormState,
  generated: ScenarioContextGenerateResponse
): ScenarioFormState {
  return {
    ...form,
    publicContext: stringifyJson(generated.public_context ?? {}),
    sideAPrivateContext: stringifyJson(generated.side_a_private_context ?? {}),
    sideBPrivateContext: stringifyJson(generated.side_b_private_context ?? {}),
    advancedOpen: true,
    generatedOnce: true
  };
}

export function ScenariosPage() {
  const query = useScenariosQuery();
  const llmCatalog = useLlmModelCatalogQuery();
  const createMutation = useCreateScenarioMutation();
  const [createForm, setCreateForm] = useState<ScenarioFormState>(EMPTY_FORM);
  const [editId, setEditId] = useState<number | null>(null);

  if (query.isLoading) {
    return <LoadingState label="Loading scenarios..." />;
  }

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => query.refetch()} />;
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Scenarios"
        description="Teacher and admin scenario management with structured public and private negotiation context."
      />

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Create scenario</h2>
        <ScenarioForm
          form={createForm}
          submitLabel={createMutation.isPending ? "Creating..." : "Create scenario"}
          onChange={setCreateForm}
          onSubmit={async () => {
            await createMutation.mutateAsync({
              name: createForm.name,
              description: createForm.description || null,
              public_context: parseJsonInput(createForm.publicContext, {}),
              side_a_private_context: parseJsonInput(createForm.sideAPrivateContext, {}),
              side_b_private_context: parseJsonInput(createForm.sideBPrivateContext, {})
            });
            setCreateForm(EMPTY_FORM);
          }}
          disabled={createMutation.isPending}
          llmCatalog={llmCatalog.data}
          llmCatalogLoading={llmCatalog.isLoading}
          llmCatalogError={llmCatalog.isError ? "LLM catalog is unavailable." : null}
        />
      </Card>

      {query.data?.length ? (
        <div className="grid gap-4">
          {query.data.map((scenario) => (
            <ScenarioCard
              key={scenario.id}
              scenario={scenario}
              isEditing={editId === scenario.id}
              onEdit={setEditId}
            />
          ))}
        </div>
      ) : (
        <EmptyState title="No scenarios" description="Create scenarios to attach negotiation context to simulations." />
      )}
    </div>
  );
}

function ScenarioCard({
  scenario,
  isEditing,
  onEdit
}: {
  scenario: ScenarioRead;
  isEditing: boolean;
  onEdit: (id: number | null) => void;
}) {
  return (
    <Card>
      {isEditing ? (
        <ScenarioEditor scenarioId={scenario.id} onClose={() => onEdit(null)} />
      ) : (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h3 className="text-base font-semibold text-slate-950">{scenario.name}</h3>
            <p className="mt-2 text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
              Description
            </p>
            <ScenarioDescriptionPreview
              testId="scenario-description-preview"
              value={scenario.description}
            />
            <p className="mt-3 text-xs text-slate-500">Updated {formatDateTime(scenario.last_updated)}</p>
          </div>
          <Button type="button" variant="secondary" onClick={() => onEdit(scenario.id)}>
            Edit
          </Button>
        </div>
      )}
    </Card>
  );
}

function ScenarioDescriptionPreview({
  value,
  testId
}: {
  value?: string | null;
  testId?: string;
}) {
  const preview = value?.trim() || "No description provided.";

  return (
    <p
      data-testid={testId}
      className="mt-2 max-h-[7.5rem] overflow-hidden whitespace-pre-line rounded-xl bg-slate-100 px-3 py-3 text-sm leading-6 text-slate-700"
    >
      {preview}
    </p>
  );
}

function ScenarioEditor({
  scenarioId,
  onClose
}: {
  scenarioId: number;
  onClose: () => void;
}) {
  const query = useScenarioAuthoringQuery(scenarioId, true);

  if (query.isLoading) {
    return <LoadingState label="Loading scenario authoring data..." />;
  }

  if (query.isError || !query.data) {
    return (
      <ErrorState
        message={query.error?.message ?? "Unable to load scenario"}
        onRetry={() => query.refetch()}
      />
    );
  }

  return <ScenarioEditorForm key={`${scenarioId}-${query.data.last_updated}`} scenario={query.data} onClose={onClose} />;
}

function ScenarioEditorForm({
  scenario,
  onClose
}: {
  scenario: ScenarioAuthoringRead;
  onClose: () => void;
}) {
  const updateMutation = useUpdateScenarioMutation(scenario.id);
  const llmCatalog = useLlmModelCatalogQuery();
  const [form, setForm] = useState<ScenarioFormState>({
    name: scenario.name,
    description: scenario.description ?? "",
    publicContext: stringifyJson(scenario.public_context),
    sideAPrivateContext: stringifyJson(scenario.side_a_private_context),
    sideBPrivateContext: stringifyJson(scenario.side_b_private_context),
    llmSelection: { provider: "openai", model: "" },
    advancedOpen: true,
    generatedOnce: true
  });

  return (
    <ScenarioForm
      form={form}
      submitLabel={updateMutation.isPending ? "Saving..." : "Save"}
      onChange={setForm}
      onSubmit={async () => {
        await updateMutation.mutateAsync({
          name: form.name,
          description: form.description || null,
          public_context: parseJsonInput(form.publicContext, {}),
          side_a_private_context: parseJsonInput(form.sideAPrivateContext, {}),
          side_b_private_context: parseJsonInput(form.sideBPrivateContext, {})
        });
        onClose();
      }}
      disabled={updateMutation.isPending}
      onCancel={onClose}
      llmCatalog={llmCatalog.data}
      llmCatalogLoading={llmCatalog.isLoading}
      llmCatalogError={llmCatalog.isError ? "LLM catalog is unavailable." : null}
    />
  );
}

function ScenarioForm({
  form,
  submitLabel,
  onChange,
  onSubmit,
  disabled,
  onCancel,
  llmCatalog,
  llmCatalogLoading,
  llmCatalogError,
}: {
  form: ScenarioFormState;
  submitLabel: string;
  onChange: (value: ScenarioFormState) => void;
  onSubmit: () => Promise<void>;
  disabled: boolean;
  onCancel?: () => void;
  llmCatalog?: LLMModelCatalogResponse;
  llmCatalogLoading: boolean;
  llmCatalogError?: string | null;
}) {
  const generateMutation = useGenerateScenarioContextMutation();
  const [message, setMessage] = useState<string | null>(null);
  const canGenerate =
    form.name.trim().length >= 3 &&
    form.description.trim().length >= 10 &&
    Boolean(form.llmSelection.model) &&
    !llmCatalogLoading &&
    !llmCatalogError;

  useEffect(() => {
    const defaultModel = getDefaultCatalogModel(llmCatalog, form.llmSelection.provider);
    if (!defaultModel || form.llmSelection.model) {
      return;
    }
    onChange({
      ...form,
      llmSelection: { ...form.llmSelection, model: defaultModel },
    });
  }, [form, llmCatalog, onChange]);

  return (
    <form
      className="mt-4 grid gap-3"
      onSubmit={async (event) => {
        event.preventDefault();
        await onSubmit();
      }}
    >
      <Field label="Name">
        <Input value={form.name} onChange={(event) => onChange({ ...form, name: event.target.value })} />
      </Field>
      <Field label="Description">
        <Textarea
          value={form.description}
          onChange={(event) => onChange({ ...form, description: event.target.value })}
        />
      </Field>
      <LlmModelSelector
        label="Generator provider"
        modelLabel="Generator model"
        catalog={llmCatalog}
        selection={form.llmSelection}
        disabled={disabled || generateMutation.isPending || llmCatalogLoading}
        onChange={(llmSelection) => onChange({ ...form, llmSelection })}
      />
      {llmCatalogError ? <p className="text-sm text-amber-700">{llmCatalogError}</p> : null}
      {!llmCatalogError && !llmCatalogLoading && !form.llmSelection.model ? (
        <p className="text-sm text-amber-700">Select a generator model before generating context.</p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="secondary"
          disabled={disabled || generateMutation.isPending || !canGenerate}
          onClick={async () => {
            const shouldReplace =
              !form.generatedOnce || window.confirm("Replace the current generated context?");
            if (!shouldReplace) {
              return;
            }
            try {
              setMessage(null);
              const generated = await generateMutation.mutateAsync({
                name: form.name.trim(),
                description: form.description.trim(),
                provider: form.llmSelection.provider,
                modelName: form.llmSelection.model,
              });
              onChange(applyGeneratedContext(form, generated));
            } catch (error) {
              setMessage(getErrorMessage(error, "Unable to generate scenario context"));
            }
          }}
        >
          {generateMutation.isPending
            ? "Generating..."
            : form.generatedOnce
              ? "Regenerate context"
              : "Generate context"}
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={() => onChange({ ...form, advancedOpen: !form.advancedOpen })}
        >
          {form.advancedOpen ? "Hide advanced context" : "Show advanced context"}
        </Button>
      </div>
      {message ? <p className="text-sm text-red-700">{message}</p> : null}
      {form.advancedOpen ? (
        <>
          <Field label="Public context JSON">
            <Textarea
              className="min-h-32 font-mono text-sm"
              value={form.publicContext}
              onChange={(event) => onChange({ ...form, publicContext: event.target.value })}
            />
          </Field>
          <Field label="Side A private context JSON">
            <Textarea
              className="min-h-32 font-mono text-sm"
              value={form.sideAPrivateContext}
              onChange={(event) => onChange({ ...form, sideAPrivateContext: event.target.value })}
            />
          </Field>
          <Field label="Side B private context JSON">
            <Textarea
              className="min-h-32 font-mono text-sm"
              value={form.sideBPrivateContext}
              onChange={(event) => onChange({ ...form, sideBPrivateContext: event.target.value })}
            />
          </Field>
        </>
      ) : null}
      <div className="flex gap-2">
        <Button type="submit" disabled={disabled}>
          {submitLabel}
        </Button>
        {onCancel ? (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </form>
  );
}
