import { useEffect, useMemo, useState } from "react";
import type {
  LLMModelCatalogResponse,
  LLMProvider,
  LLMSelection,
  RagProfileCopy,
  RagProfileDefinitionRead,
  RagProfileFieldDefinitionRead,
  RagProfileRead,
} from "@/api/types";
import { getErrorMessage } from "@/api/client";
import {
  useCopyRagProfileMutation,
  useCreateRagProfileMutation,
  useDeleteRagProfileMutation,
  useRagProfileDefinitionsQuery,
  useRagProfilesQuery,
  useUpdateRagProfileMutation,
} from "@/features/ragProfiles/ragProfileQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { DataTable } from "@/components/common/DataTable";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { LlmModelSelector, getDefaultCatalogModel } from "@/components/llm/LlmModelSelector";
import { formatDateTime } from "@/utils/format";
import { useKnowledgeGraphsQuery } from "@/features/knowledgeGraphs/knowledgeGraphQueries";
import { useLlmModelCatalogQuery } from "@/features/llmModels/llmModelQueries";

type ProfileCreateState = {
  name: string;
  strategy: string;
  fieldValues: Record<string, string>;
  llmComponents: Record<string, LLMSelection>;
  knowledgeGraphIndexId: string;
};

const RAG_LLM_COMPONENTS = [
  { key: "document_grader", label: "Document grader" },
  { key: "rewrite", label: "Rewrite" },
  { key: "generate", label: "Generate" },
  { key: "hallucination_grader", label: "Hallucination grader" },
  { key: "answer_grader", label: "Answer grader" },
  { key: "fallback", label: "Fallback" },
] as const;

type ActiveAction =
  | { type: "edit"; profileId: number }
  | { type: "copy"; profileId: number }
  | { type: "delete"; profileId: number }
  | null;

export function RagProfilesPage() {
  const query = useRagProfilesQuery();
  const definitionsQuery = useRagProfileDefinitionsQuery();
  const createMutation = useCreateRagProfileMutation();
  const knowledgeGraphsQuery = useKnowledgeGraphsQuery();
  const llmCatalogQuery = useLlmModelCatalogQuery();
  const [createForm, setCreateForm] = useState<ProfileCreateState>({
    name: "",
    strategy: "crag",
    fieldValues: {},
    llmComponents: buildLlmComponentValues(),
    knowledgeGraphIndexId: "",
  });
  const [message, setMessage] = useState<string | null>(null);
  const [activeAction, setActiveAction] = useState<ActiveAction>(null);

  const definitions = definitionsQuery.data ?? [];
  const createDefinition = getDefinition(definitions, createForm.strategy);
  const activeProfile = useMemo(
    () => query.data?.find((profile) => profile.id === activeAction?.profileId) ?? null,
    [activeAction?.profileId, query.data],
  );

  useEffect(() => {
    if (!definitions.length) {
      return;
    }

    setCreateForm((current) => {
      const nextDefinition = getDefinition(definitions, current.strategy) ?? definitions[0];
      if (!nextDefinition) {
        return current;
      }
      if (current.strategy === nextDefinition.strategy && Object.keys(current.fieldValues).length) {
        return current;
      }
      return {
        ...current,
        strategy: nextDefinition.strategy,
        fieldValues: buildFieldValues(nextDefinition),
        llmComponents: buildLlmComponentValues(current.llmComponents),
      };
    });
  }, [definitions]);

  useEffect(() => {
    const defaultModel = getDefaultCatalogModel(llmCatalogQuery.data, "openai");
    if (!defaultModel) {
      return;
    }
    setCreateForm((current) => {
      const llmComponents = buildLlmComponentValues(current.llmComponents, defaultModel);
      if (areLlmComponentValuesEqual(current.llmComponents, llmComponents)) {
        return current;
      }
      return { ...current, llmComponents };
    });
  }, [llmCatalogQuery.data]);

  if (query.isLoading || definitionsQuery.isLoading || knowledgeGraphsQuery.isLoading) {
    return <LoadingState label="Loading RAG profiles..." />;
  }

  const error = query.isError
    ? query.error
    : definitionsQuery.isError
      ? definitionsQuery.error
      : knowledgeGraphsQuery.isError
        ? knowledgeGraphsQuery.error
        : null;
  if (error) {
    return (
      <ErrorState
        message={error.message}
        onRetry={() => {
          void query.refetch();
          void definitionsQuery.refetch();
          void knowledgeGraphsQuery.refetch();
          void llmCatalogQuery.refetch();
        }}
      />
    );
  }

  const profiles = query.data ?? [];
  const builtGraphs = (knowledgeGraphsQuery.data ?? []).filter((graph) => graph.status === "built");

  return (
    <div className="grid gap-6">
      <PageHeader
        title="RAG Profiles"
        description="Admin-owned retrieval strategies that simulations can select at creation time."
      />

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Create RAG profile</h2>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">
              Store CRAG retrieval settings once and reuse them across simulation setup.
            </p>
          </div>
          <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
            <strong className="block text-slate-950">{profiles.length}</strong>
            stored profile{profiles.length === 1 ? "" : "s"}
          </div>
        </div>

        <form
          className="mt-5 grid gap-3"
          onSubmit={async (event) => {
            event.preventDefault();
            setMessage(null);
            try {
              const definition = requireDefinition(createDefinition, createForm.strategy);
              await createMutation.mutateAsync({
                name: createForm.name.trim(),
                strategy: definition.strategy,
                config: packProfileConfig(definition, createForm.fieldValues, createForm.llmComponents),
                knowledge_graph_index_id:
                  definition.strategy === "graphrag"
                    ? Number(createForm.knowledgeGraphIndexId)
                    : null,
              });
              setCreateForm({
                name: "",
                strategy: definition.strategy,
                fieldValues: buildFieldValues(definition),
                llmComponents: buildLlmComponentValues(createForm.llmComponents),
                knowledgeGraphIndexId: "",
              });
              setMessage("RAG profile created.");
            } catch (error) {
              setMessage(getErrorMessage(error, "Unable to create RAG profile"));
            }
          }}
        >
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Name">
              <Input
                value={createForm.name}
                onChange={(event) => setCreateForm((current) => ({ ...current, name: event.target.value }))}
                required
              />
            </Field>
            <Field label="Strategy">
              <Select
                value={createForm.strategy}
                onChange={(event) => {
                  const nextDefinition = getDefinition(definitions, event.target.value);
                  setCreateForm((current) => ({
                    ...current,
                    strategy: event.target.value,
                    fieldValues: nextDefinition ? buildFieldValues(nextDefinition) : {},
                    knowledgeGraphIndexId: "",
                  }));
                }}
                required
              >
                {definitions.map((definition) => (
                  <option key={definition.strategy} value={definition.strategy}>
                    {definition.label}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          {createDefinition ? (
            <>
              {createDefinition.strategy === "graphrag" ? (
                <Field label="Knowledge graph" hint="Only built graphs can be selected.">
                  <Select
                    value={createForm.knowledgeGraphIndexId}
                    onChange={(event) =>
                      setCreateForm((current) => ({
                        ...current,
                        knowledgeGraphIndexId: event.target.value,
                      }))
                    }
                    required
                  >
                    <option value="">Select built graph</option>
                    {builtGraphs.map((graph) => (
                      <option key={graph.id} value={graph.id}>{graph.name}</option>
                    ))}
                  </Select>
                </Field>
              ) : null}
              <DefinitionFields
                definition={createDefinition}
                fieldValues={createForm.fieldValues}
                onChange={(fieldName, value) =>
                  setCreateForm((current) => ({
                    ...current,
                    fieldValues: { ...current.fieldValues, [fieldName]: value },
                  }))
                }
              />
              <LlmComponentsFields
                catalog={llmCatalogQuery.data}
                catalogLoading={llmCatalogQuery.isLoading}
                catalogError={llmCatalogQuery.isError ? getErrorMessage(llmCatalogQuery.error, "LLM catalog is unavailable.") : null}
                values={createForm.llmComponents}
                onChange={(component, selection) =>
                  setCreateForm((current) => ({
                    ...current,
                    llmComponents: { ...current.llmComponents, [component]: selection },
                  }))
                }
              />
            </>
          ) : null}
          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="submit"
              disabled={
                createMutation.isPending ||
                llmCatalogQuery.isLoading ||
                llmCatalogQuery.isError ||
                !hasAllLlmComponentModels(createForm.llmComponents)
              }
            >
              {createMutation.isPending ? "Creating..." : "Create profile"}
            </Button>
            {message ? <span className="text-sm text-slate-600">{message}</span> : null}
          </div>
        </form>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Stored profiles</h2>
        <p className="mt-2 text-sm text-slate-600">
          Profiles lock after simulation use so retrieval behavior stays stable for existing work.
        </p>

        {profiles.length ? (
          <div className="mt-4 grid gap-4">
            <DataTable
              rows={profiles}
              columns={[
                {
                  key: "name",
                  header: "Profile",
                  render: (profile) => (
                    <div>
                      <div className="font-medium text-slate-950">{profile.name}</div>
                      <p className="mt-1 text-xs text-slate-500">Created {formatDateTime(profile.created_at)}</p>
                    </div>
                  ),
                },
                {
                  key: "strategy",
                  header: "Strategy",
                  render: (profile) => (
                    <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
                      {profile.strategy}
                    </span>
                  ),
                },
                {
                  key: "config",
                  header: "Config",
                  render: (profile) => (
                    <div className="grid gap-1 text-xs text-slate-600">
                      <span>top_k {getConfigValue(profile, "top_k")}</span>
                      <span>reranker {getConfigValue(profile, "reranker")}</span>
                      <span>top_n {getConfigValue(profile, "top_n")}</span>
                      <span>rewrite attempts {getConfigValue(profile, "max_rewrite_attempts")}</span>
                      {profile.knowledge_graph_index_id ? (
                        <span>graph #{profile.knowledge_graph_index_id}</span>
                      ) : null}
                    </div>
                  ),
                },
                {
                  key: "usage",
                  header: "Usage",
                  render: (profile) => (
                    <div className="text-sm">
                      <div className="font-medium text-slate-950">{hasSimulations(profile) ? "In use" : "Unused"}</div>
                      <p className="mt-1 text-xs text-slate-500">
                        {getSimulationCount(profile)} simulation{getSimulationCount(profile) === 1 ? "" : "s"}
                      </p>
                      {hasSimulations(profile) ? (
                        <p className="mt-1 text-xs text-amber-700">Locked after simulation use.</p>
                      ) : null}
                    </div>
                  ),
                },
                {
                  key: "updated",
                  header: "Last updated",
                  render: (profile) => <span className="text-sm text-slate-600">{formatDateTime(profile.last_updated)}</span>,
                },
                {
                  key: "actions",
                  header: "Actions",
                  render: (profile) => (
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" variant="secondary" onClick={() => setActiveAction({ type: "edit", profileId: profile.id })}>
                        Edit
                      </Button>
                      <Button type="button" variant="secondary" onClick={() => setActiveAction({ type: "copy", profileId: profile.id })}>
                        Copy
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        disabled={hasSimulations(profile)}
                        onClick={() => setActiveAction({ type: "delete", profileId: profile.id })}
                      >
                        Delete
                      </Button>
                    </div>
                  ),
                },
              ]}
            />

            {activeAction && activeProfile ? (
              <ActionPanel
                key={`${activeAction.type}-${activeProfile.id}`}
                action={activeAction}
                profile={activeProfile}
                definitions={definitions}
                knowledgeGraphs={builtGraphs}
                llmCatalog={llmCatalogQuery.data}
                llmCatalogLoading={llmCatalogQuery.isLoading}
                llmCatalogError={llmCatalogQuery.isError ? getErrorMessage(llmCatalogQuery.error, "LLM catalog is unavailable.") : null}
                onClose={() => setActiveAction(null)}
              />
            ) : null}
          </div>
        ) : (
          <div className="mt-4">
            <EmptyState
              title="No RAG profiles"
              description="Create the first reusable retrieval profile here, then select it during simulation setup."
            />
          </div>
        )}
      </Card>
    </div>
  );
}

function ActionPanel({
  action,
  profile,
  definitions,
  knowledgeGraphs,
  llmCatalog,
  llmCatalogLoading,
  llmCatalogError,
  onClose,
}: {
  action: Exclude<ActiveAction, null>;
  profile: RagProfileRead;
  definitions: RagProfileDefinitionRead[];
  knowledgeGraphs: Array<{ id: number; name: string }>;
  llmCatalog?: LLMModelCatalogResponse;
  llmCatalogLoading: boolean;
  llmCatalogError: string | null;
  onClose: () => void;
}) {
  if (action.type === "edit") {
    return <EditProfilePanel profile={profile} definitions={definitions} knowledgeGraphs={knowledgeGraphs} llmCatalog={llmCatalog} llmCatalogLoading={llmCatalogLoading} llmCatalogError={llmCatalogError} onClose={onClose} />;
  }
  if (action.type === "copy") {
    return <CopyProfilePanel profile={profile} definitions={definitions} knowledgeGraphs={knowledgeGraphs} llmCatalog={llmCatalog} llmCatalogLoading={llmCatalogLoading} llmCatalogError={llmCatalogError} onClose={onClose} />;
  }
  return <DeleteProfilePanel profile={profile} onClose={onClose} />;
}

function EditProfilePanel({
  profile,
  definitions,
  knowledgeGraphs,
  llmCatalog,
  llmCatalogLoading,
  llmCatalogError,
  onClose,
}: {
  profile: RagProfileRead;
  definitions: RagProfileDefinitionRead[];
  knowledgeGraphs: Array<{ id: number; name: string }>;
  llmCatalog?: LLMModelCatalogResponse;
  llmCatalogLoading: boolean;
  llmCatalogError: string | null;
  onClose: () => void;
}) {
  const updateMutation = useUpdateRagProfileMutation(profile.id);
  const definition = requireDefinition(getDefinition(definitions, profile.strategy), profile.strategy);
  const [form, setForm] = useState<ProfileCreateState>({
    name: profile.name,
    strategy: profile.strategy,
    fieldValues: buildFieldValues(definition, profile.config),
    llmComponents: buildLlmComponentValues(profile.config?.llm_components),
    knowledgeGraphIndexId: profile.knowledge_graph_index_id ? String(profile.knowledge_graph_index_id) : "",
  });
  const [message, setMessage] = useState<string | null>(null);
  const used = hasSimulations(profile);

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <h3 className="text-base font-semibold text-slate-950">Edit profile</h3>
      <p className="mt-2 text-sm text-slate-600">
        {used
          ? "This profile is already referenced by simulations, so editing is locked."
          : "Update the stored retrieval settings in place."}
      </p>
      <form
        className="mt-4 grid gap-3"
        onSubmit={async (event) => {
          event.preventDefault();
          setMessage(null);
          try {
            await updateMutation.mutateAsync({
              name: form.name.trim(),
              strategy: definition.strategy,
              config: packProfileConfig(definition, form.fieldValues, form.llmComponents),
              knowledge_graph_index_id:
                definition.strategy === "graphrag" ? Number(form.knowledgeGraphIndexId) : null,
            });
            onClose();
          } catch (error) {
            setMessage(getErrorMessage(error, "Unable to update RAG profile"));
          }
        }}
      >
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Name">
            <Input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} required />
          </Field>
          <Field label="Strategy">
            <Input value={form.strategy} disabled required />
          </Field>
        </div>
        {definition.strategy === "graphrag" ? (
          <Field label="Knowledge graph">
            <Select
              value={form.knowledgeGraphIndexId}
              disabled={used}
              onChange={(event) => setForm((current) => ({ ...current, knowledgeGraphIndexId: event.target.value }))}
              required
            >
              <option value="">Select built graph</option>
              {knowledgeGraphs.map((graph) => <option key={graph.id} value={graph.id}>{graph.name}</option>)}
            </Select>
          </Field>
        ) : null}
        <DefinitionFields
          definition={definition}
          fieldValues={form.fieldValues}
          disabled={used}
          onChange={(fieldName, value) =>
            setForm((current) => ({
              ...current,
              fieldValues: { ...current.fieldValues, [fieldName]: value },
            }))
          }
        />
        <LlmComponentsFields
          catalog={llmCatalog}
          catalogLoading={llmCatalogLoading}
          catalogError={llmCatalogError}
          values={form.llmComponents}
          disabled={used}
          onChange={(component, selection) =>
            setForm((current) => ({
              ...current,
              llmComponents: { ...current.llmComponents, [component]: selection },
            }))
          }
        />
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="submit"
            disabled={
              updateMutation.isPending ||
              used ||
              llmCatalogLoading ||
              Boolean(llmCatalogError) ||
              !hasAllLlmComponentModels(form.llmComponents)
            }
          >
            {updateMutation.isPending ? "Saving..." : "Save changes"}
          </Button>
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          {message ? <span className="text-sm text-slate-600">{message}</span> : null}
        </div>
      </form>
    </div>
  );
}

function CopyProfilePanel({
  profile,
  definitions,
  knowledgeGraphs,
  llmCatalog,
  llmCatalogLoading,
  llmCatalogError,
  onClose,
}: {
  profile: RagProfileRead;
  definitions: RagProfileDefinitionRead[];
  knowledgeGraphs: Array<{ id: number; name: string }>;
  llmCatalog?: LLMModelCatalogResponse;
  llmCatalogLoading: boolean;
  llmCatalogError: string | null;
  onClose: () => void;
}) {
  const copyMutation = useCopyRagProfileMutation(profile.id);
  const definition = requireDefinition(getDefinition(definitions, profile.strategy), profile.strategy);
  const [form, setForm] = useState<ProfileCreateState>({
    name: `${profile.name} Copy`,
    strategy: profile.strategy,
    fieldValues: buildFieldValues(definition, profile.config),
    llmComponents: buildLlmComponentValues(profile.config?.llm_components),
    knowledgeGraphIndexId: profile.knowledge_graph_index_id ? String(profile.knowledge_graph_index_id) : "",
  });
  const [message, setMessage] = useState<string | null>(null);

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <h3 className="text-base font-semibold text-slate-950">Copy profile</h3>
      <p className="mt-2 text-sm text-slate-600">Create a new variant from the selected CRAG settings.</p>
      <form
        className="mt-4 grid gap-3"
        onSubmit={async (event) => {
          event.preventDefault();
          setMessage(null);
          try {
            await copyMutation.mutateAsync({
              name: form.name.trim(),
              strategy: definition.strategy,
              config: packProfileConfig(definition, form.fieldValues, form.llmComponents),
              knowledge_graph_index_id:
                definition.strategy === "graphrag" ? Number(form.knowledgeGraphIndexId) : null,
            } satisfies RagProfileCopy);
            onClose();
          } catch (error) {
            setMessage(getErrorMessage(error, "Unable to copy RAG profile"));
          }
        }}
      >
        <Field label="New name">
          <Input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} required />
        </Field>
        {definition.strategy === "graphrag" ? (
          <Field label="Knowledge graph">
            <Select
              value={form.knowledgeGraphIndexId}
              onChange={(event) => setForm((current) => ({ ...current, knowledgeGraphIndexId: event.target.value }))}
              required
            >
              <option value="">Select built graph</option>
              {knowledgeGraphs.map((graph) => <option key={graph.id} value={graph.id}>{graph.name}</option>)}
            </Select>
          </Field>
        ) : null}
        <DefinitionFields
          definition={definition}
          fieldValues={form.fieldValues}
          onChange={(fieldName, value) =>
            setForm((current) => ({
              ...current,
              fieldValues: { ...current.fieldValues, [fieldName]: value },
            }))
          }
        />
        <LlmComponentsFields
          catalog={llmCatalog}
          catalogLoading={llmCatalogLoading}
          catalogError={llmCatalogError}
          values={form.llmComponents}
          onChange={(component, selection) =>
            setForm((current) => ({
              ...current,
              llmComponents: { ...current.llmComponents, [component]: selection },
            }))
          }
        />
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="submit"
            disabled={
              copyMutation.isPending ||
              llmCatalogLoading ||
              Boolean(llmCatalogError) ||
              !hasAllLlmComponentModels(form.llmComponents)
            }
          >
            {copyMutation.isPending ? "Copying..." : "Create copy"}
          </Button>
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          {message ? <span className="text-sm text-slate-600">{message}</span> : null}
        </div>
      </form>
    </div>
  );
}

function DeleteProfilePanel({ profile, onClose }: { profile: RagProfileRead; onClose: () => void }) {
  const deleteMutation = useDeleteRagProfileMutation(profile.id);
  const [message, setMessage] = useState<string | null>(null);

  return (
    <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4">
      <h3 className="text-base font-semibold text-slate-950">Delete profile</h3>
      <p className="mt-2 text-sm text-slate-600">
        Delete <strong>{profile.name}</strong> only if it is not referenced by simulations.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button
          type="button"
          disabled={deleteMutation.isPending}
          onClick={async () => {
            setMessage(null);
            try {
              await deleteMutation.mutateAsync();
              onClose();
            } catch (error) {
              setMessage(getErrorMessage(error, "Unable to delete RAG profile"));
            }
          }}
        >
          {deleteMutation.isPending ? "Deleting..." : "Confirm delete"}
        </Button>
        <Button type="button" variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        {message ? <span className="text-sm text-slate-600">{message}</span> : null}
      </div>
    </div>
  );
}

function hasSimulations(profile: RagProfileRead) {
  return getSimulationCount(profile) > 0;
}

function getSimulationCount(profile: RagProfileRead) {
  return profile.simulation_ids?.length ?? 0;
}

function getConfigValue(profile: RagProfileRead, key: string) {
  const value = profile.config?.[key];
  return value == null ? "-" : String(value);
}

function DefinitionFields({
  definition,
  fieldValues,
  onChange,
  disabled = false,
}: {
  definition: RagProfileDefinitionRead;
  fieldValues: Record<string, string>;
  onChange: (fieldName: string, value: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {definition.fields.map((field: RagProfileFieldDefinitionRead) => (
        <Field key={field.name} label={field.label} hint={field.help_text ?? undefined}>
          {field.kind === "enum" ? (
            <Select
              value={fieldValues[field.name] ?? String(field.default)}
              disabled={disabled}
              onChange={(event) => onChange(field.name, event.target.value)}
            >
              {field.options.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </Select>
          ) : (
            <Input
              type="number"
              min={field.minimum ?? undefined}
              max={field.maximum ?? undefined}
              disabled={disabled}
              value={fieldValues[field.name] ?? String(field.default)}
              onChange={(event) => onChange(field.name, event.target.value)}
            />
          )}
        </Field>
      ))}
    </div>
  );
}

function LlmComponentsFields({
  catalog,
  catalogLoading = false,
  catalogError = null,
  values,
  onChange,
  disabled = false,
}: {
  catalog?: LLMModelCatalogResponse;
  catalogLoading?: boolean;
  catalogError?: string | null;
  values: Record<string, LLMSelection>;
  onChange: (component: string, selection: LLMSelection) => void;
  disabled?: boolean;
}) {
  return (
    <div className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div>
        <h3 className="text-sm font-semibold text-slate-950">LLM components</h3>
        {catalogLoading ? <p className="mt-1 text-xs text-slate-500">Loading models...</p> : null}
        {catalogError ? <p className="mt-1 text-xs text-amber-700">{catalogError}</p> : null}
        {typeof catalog?.gpu_memory_gib === "number" ? (
          <p className="mt-1 text-xs text-slate-500">Ollama GPU memory: {catalog.gpu_memory_gib} GiB</p>
        ) : null}
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {RAG_LLM_COMPONENTS.map((component) => (
          <LlmModelSelector
            key={component.key}
            label={component.label}
            modelLabel={`${component.label} model`}
            catalog={catalog}
            selection={values[component.key] ?? { provider: "openai", model: getDefaultCatalogModel(catalog, "openai") ?? "" }}
            disabled={disabled || catalogLoading}
            onChange={(selection) => onChange(component.key, selection)}
            metadataMode="error-only"
            variant="plain"
          />
        ))}
      </div>
    </div>
  );
}

function getDefinition(definitions: RagProfileDefinitionRead[], strategy: string) {
  return definitions.find((definition) => definition.strategy === strategy) ?? null;
}

function requireDefinition(definition: RagProfileDefinitionRead | null, strategy: string) {
  if (!definition) {
    throw new Error(`Unknown RAG profile definition for strategy '${strategy}'`);
  }
  return definition;
}

function buildFieldValues(definition: RagProfileDefinitionRead, config?: Record<string, unknown>) {
  return Object.fromEntries(
    definition.fields.map((field) => [field.name, String(config?.[field.name] ?? field.default ?? "")]),
  );
}

function buildLlmComponentValues(raw?: unknown, defaultModel = ""): Record<string, LLMSelection> {
  const source = isRecord(raw) ? raw : {};
  return Object.fromEntries(
    RAG_LLM_COMPONENTS.map((component) => {
      const value = source[component.key];
      const selection = isRecord(value)
        ? {
            provider: (value.provider === "ollama" ? "ollama" : "openai") as LLMProvider,
            model: typeof value.model === "string" ? value.model : defaultModel,
          }
        : { provider: "openai" as LLMProvider, model: defaultModel };
      return [component.key, selection];
    }),
  ) as Record<string, LLMSelection>;
}

function areLlmComponentValuesEqual(
  left: Record<string, LLMSelection>,
  right: Record<string, LLMSelection>,
) {
  return RAG_LLM_COMPONENTS.every((component) => {
    const leftSelection = left[component.key];
    const rightSelection = right[component.key];
    return leftSelection?.provider === rightSelection?.provider && leftSelection?.model === rightSelection?.model;
  });
}

function hasAllLlmComponentModels(values: Record<string, LLMSelection>) {
  return RAG_LLM_COMPONENTS.every((component) => Boolean(values[component.key]?.model?.trim()));
}

function packProfileConfig(
  definition: RagProfileDefinitionRead,
  fieldValues: Record<string, string>,
  llmComponents: Record<string, LLMSelection>,
) {
  return {
    ...Object.fromEntries(
    definition.fields.map((field) => {
      const raw = fieldValues[field.name] ?? "";
      if (field.kind === "int") {
        return [field.name, Number(raw)];
      }
      return [field.name, raw];
    }),
    ),
    llm_components: Object.fromEntries(
      RAG_LLM_COMPONENTS.map((component) => [component.key, llmComponents[component.key]]),
    ),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}
