import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import { useCreatePersonaMutation, usePersonasQuery, useUpdatePersonaMutation } from "@/features/counterpartPersonas/personaQueries";
import type { CounterpartPersonaRead } from "@/api/types";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { formatDateTime } from "@/utils/format";

const personaMarkdownComponents: Components = {
  h1: ({ children }) => <h4 className="mb-1 mt-0 text-sm font-semibold text-slate-950">{children}</h4>,
  h2: ({ children }) => <h4 className="mb-1 mt-0 text-sm font-semibold text-slate-950">{children}</h4>,
  h3: ({ children }) => <h4 className="mb-1 mt-0 text-sm font-semibold text-slate-950">{children}</h4>,
  p: ({ children }) => <p className="my-1">{children}</p>,
  ul: ({ children }) => <ul className="my-1 list-disc space-y-0.5 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="my-1 list-decimal space-y-0.5 pl-5">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  a: ({ children, href }) => (
    <a className="font-medium text-sky-700 underline" href={href} rel="noreferrer" target="_blank">
      {children}
    </a>
  ),
  code: ({ children }) => <code className="rounded bg-slate-200 px-1 py-0.5 text-xs text-slate-800">{children}</code>,
  pre: ({ children }) => <pre className="my-2 overflow-x-auto rounded-lg bg-slate-900 px-3 py-2 text-xs text-slate-100">{children}</pre>,
  blockquote: ({ children }) => <blockquote className="my-2 border-l-2 border-slate-300 pl-3 text-slate-600">{children}</blockquote>
};

export function PersonasPage() {
  const query = usePersonasQuery();
  const createMutation = useCreatePersonaMutation();
  const [editId, setEditId] = useState<number | null>(null);
  const [createForm, setCreateForm] = useState({ name: "", description: "" });

  if (query.isLoading) {
    return <LoadingState label="Loading personas..." />;
  }

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => query.refetch()} />;
  }

  return (
    <div className="grid gap-6">
      <PageHeader title="Personas" description="Counterpart persona list/create/edit patterns backed by the current API." />

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Create persona</h2>
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
              required
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
              {createMutation.isPending ? "Creating..." : "Create persona"}
            </Button>
          </div>
        </form>
      </Card>

      {query.data?.length ? (
        <div className="grid gap-4">
          {query.data.map((persona) => (
            <PersonaCard key={persona.id} persona={persona} isEditing={editId === persona.id} onEdit={setEditId} />
          ))}
        </div>
      ) : (
        <EmptyState title="No personas" description="Create a counterpart persona to reuse during simulation setup." />
      )}
    </div>
  );
}

function PersonaCard({
  persona,
  isEditing,
  onEdit
}: {
  persona: CounterpartPersonaRead;
  isEditing: boolean;
  onEdit: (id: number | null) => void;
}) {
  const updateMutation = useUpdatePersonaMutation(persona.id);
  const [name, setName] = useState(persona.name);
  const [description, setDescription] = useState(persona.description ?? "");

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
          <div className="min-w-0 flex-1">
            <h3 className="text-base font-semibold text-slate-950">{persona.name}</h3>
            <PersonaDescriptionPreview value={persona.description} />
            <p className="mt-2 text-xs text-slate-500">Updated {formatDateTime(persona.last_updated)}</p>
          </div>
          <Button type="button" variant="secondary" onClick={() => onEdit(persona.id)}>
            Edit
          </Button>
        </div>
      )}
    </Card>
  );
}

function PersonaDescriptionPreview({ value }: { value?: string | null }) {
  const content = value?.trim() || "No description";
  const hasDescription = Boolean(value?.trim());
  const [expanded, setExpanded] = useState(false);
  const [measuredOverflow, setMeasuredOverflow] = useState(false);
  const previewRef = useRef<HTMLDivElement>(null);
  const sourceSuggestsOverflow = content.split(/\r?\n/).length > 7 || content.length > 360;
  const canExpand = hasDescription && (sourceSuggestsOverflow || measuredOverflow);
  const isPreviewed = hasDescription && !expanded;
  const isCollapsed = canExpand && !expanded;

  useEffect(() => {
    setMeasuredOverflow(false);
  }, [content]);

  useEffect(() => {
    const preview = previewRef.current;
    if (!preview || !hasDescription || expanded) {
      return;
    }

    const measureOverflow = () => {
      setMeasuredOverflow(preview.scrollHeight > preview.clientHeight + 1);
    };

    measureOverflow();
    const resizeObserver = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measureOverflow);
    resizeObserver?.observe(preview);
    return () => resizeObserver?.disconnect();
  }, [content, hasDescription, expanded]);

  return (
    <div className="mt-2">
      <div className="relative rounded-xl bg-slate-100 px-3 py-3">
        <div
          ref={previewRef}
          data-testid="persona-description-preview"
          className={[
            "max-w-none text-sm leading-6 text-slate-700",
            isPreviewed ? "max-h-[10.5rem] overflow-hidden" : ""
          ].join(" ")}
        >
          <ReactMarkdown components={personaMarkdownComponents}>{content}</ReactMarkdown>
        </div>
        {isCollapsed ? (
          <div className="pointer-events-none absolute inset-x-3 bottom-3 flex justify-end bg-gradient-to-t from-slate-100 via-slate-100/95 to-transparent pt-8 text-sm font-semibold text-slate-500">
            ...
          </div>
        ) : null}
      </div>
      {canExpand ? (
        <Button type="button" variant="secondary" className="mt-2" onClick={() => setExpanded((current) => !current)}>
          {expanded ? "Show less" : "Show more"}
        </Button>
      ) : null}
    </div>
  );
}
