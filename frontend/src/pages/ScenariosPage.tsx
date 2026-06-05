import { useState } from "react";
import { useCreateScenarioMutation, useScenariosQuery, useUpdateScenarioMutation } from "@/features/scenarios/scenarioQueries";
import type { ScenarioRead } from "@/api/types";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { formatDateTime } from "@/utils/format";

export function ScenariosPage() {
  const query = useScenariosQuery();
  const createMutation = useCreateScenarioMutation();
  const [createForm, setCreateForm] = useState({ name: "", description: "" });
  const [editId, setEditId] = useState<number | null>(null);

  if (query.isLoading) {
    return <LoadingState label="Loading scenarios..." />;
  }

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => query.refetch()} />;
  }

  return (
    <div className="grid gap-6">
      <PageHeader title="Scenarios" description="Teacher and admin scenario management with real create and update endpoints." />

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Create scenario</h2>
        <form
          className="mt-4 grid gap-3"
          onSubmit={async (event) => {
            event.preventDefault();
            await createMutation.mutateAsync(createForm);
            setCreateForm({ name: "", description: "" });
          }}
        >
          <Field label="Name">
            <Input
              value={createForm.name}
              onChange={(event) => setCreateForm((current) => ({ ...current, name: event.target.value }))}
            />
          </Field>
          <Field label="Description">
            <Textarea
              value={createForm.description}
              onChange={(event) => setCreateForm((current) => ({ ...current, description: event.target.value }))}
            />
          </Field>
          <div>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating..." : "Create scenario"}
            </Button>
          </div>
        </form>
      </Card>

      {query.data?.length ? (
        <div className="grid gap-4">
          {query.data.map((scenario) => (
            <ScenarioCard key={scenario.id} scenario={scenario} isEditing={editId === scenario.id} onEdit={setEditId} />
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
  const updateMutation = useUpdateScenarioMutation(scenario.id);
  const [name, setName] = useState(scenario.name);
  const [description, setDescription] = useState(scenario.description ?? "");

  return (
    <Card>
      {isEditing ? (
        <form
          className="grid gap-3"
          onSubmit={async (event) => {
            event.preventDefault();
            await updateMutation.mutateAsync({ name, description });
            onEdit(null);
          }}
        >
          <Field label="Name">
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
          <Field label="Description">
            <Textarea value={description} onChange={(event) => setDescription(event.target.value)} />
          </Field>
          <div className="flex gap-2">
            <Button type="submit" disabled={updateMutation.isPending}>
              Save
            </Button>
            <Button type="button" variant="secondary" onClick={() => onEdit(null)}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-slate-950">{scenario.name}</h3>
            <p className="mt-1 text-sm text-slate-600">{scenario.description ?? "No description"}</p>
            <p className="mt-2 text-xs text-slate-500">Updated {formatDateTime(scenario.last_updated)}</p>
          </div>
          <Button type="button" variant="secondary" onClick={() => onEdit(scenario.id)}>
            Edit
          </Button>
        </div>
      )}
    </Card>
  );
}
