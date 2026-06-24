import { useState, type ReactNode } from "react";
import { useCreatePromptMutation, usePromptsQuery, useUpdatePromptMutation } from "@/features/prompts/promptQueries";
import type { PromptRead } from "@/api/types";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { parseJsonInput, stringifyJson } from "@/utils/format";

const PROMPT_TEMPLATE_KEYS = ["template", "prompt", "content", "system", "coach", "counterpart", "evaluator"];
const PROMPT_TEMPLATE_EXAMPLE = `{
  "template": "Add stricter negotiation coaching around {messages}."
}`;

export function PromptsPage() {
  const query = usePromptsQuery();
  const createMutation = useCreatePromptMutation();
  const [createForm, setCreateForm] = useState({
    name: "",
    description: "",
    messages: "{}",
    isSystem: false
  });
  const [editId, setEditId] = useState<number | null>(null);
  const [createMessagesError, setCreateMessagesError] = useState<string | null>(null);

  if (query.isLoading) {
    return <LoadingState label="Loading prompts..." />;
  }

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => query.refetch()} />;
  }

  return (
    <div className="grid gap-6">
      <PageHeader title="Prompts" description="Admin-only prompt registry: custom prompts inject into system prompts. Experimental, use with caution." />

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Create prompt</h2>
        <form
          className="mt-4 grid gap-3"
          onSubmit={async (event) => {
            event.preventDefault();
            setCreateMessagesError(null);
            let messages: Record<string, unknown>;
            try {
              messages = parseJsonInput<Record<string, unknown>>(createForm.messages, {});
            } catch {
              setCreateMessagesError("Prompt Template JSON must be valid JSON.");
              return;
            }
            await createMutation.mutateAsync({
              name: createForm.name,
              description: createForm.description || null,
              messages,
              is_system: createForm.isSystem
            });
            setCreateForm({ name: "", description: "", messages: "{}", isSystem: false });
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
          <PromptTemplateJsonField error={createMessagesError}>
            <Textarea
              aria-label="Prompt Template JSON"
              value={createForm.messages}
              onChange={(event) => {
                setCreateMessagesError(null);
                setCreateForm((current) => ({ ...current, messages: event.target.value }));
              }}
            />
          </PromptTemplateJsonField>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={createForm.isSystem}
              onChange={(event) => setCreateForm((current) => ({ ...current, isSystem: event.target.checked }))}
            />
            System prompt
          </label>
          <div>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating..." : "Create prompt"}
            </Button>
          </div>
        </form>
      </Card>

      {query.data?.length ? (
        <div className="grid gap-4">
          {query.data.map((prompt) => (
            <PromptCard key={prompt.id} prompt={prompt} isEditing={editId === prompt.id} onEdit={setEditId} />
          ))}
        </div>
      ) : (
        <EmptyState title="No prompts" description="Create prompts before assigning them to simulations." />
      )}
    </div>
  );
}

function PromptCard({
  prompt,
  isEditing,
  onEdit
}: {
  prompt: PromptRead;
  isEditing: boolean;
  onEdit: (id: number | null) => void;
}) {
  const updateMutation = useUpdatePromptMutation(prompt.id);
  const [name, setName] = useState(prompt.name);
  const [description, setDescription] = useState(prompt.description ?? "");
  const [messages, setMessages] = useState(stringifyJson(prompt.messages));
  const [isSystem, setIsSystem] = useState(prompt.is_system);
  const [messagesError, setMessagesError] = useState<string | null>(null);

  return (
    <Card>
      {isEditing ? (
        <form
          className="grid gap-3"
          onSubmit={async (event) => {
            event.preventDefault();
            setMessagesError(null);
            let parsedMessages: Record<string, unknown>;
            try {
              parsedMessages = parseJsonInput<Record<string, unknown>>(messages, {});
            } catch {
              setMessagesError("Prompt Template JSON must be valid JSON.");
              return;
            }
            await updateMutation.mutateAsync({
              name,
              description,
              messages: parsedMessages,
              is_system: isSystem
            });
            onEdit(null);
          }}
        >
          <Field label="Name">
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
          <Field label="Description">
            <Textarea value={description} onChange={(event) => setDescription(event.target.value)} />
          </Field>
          <PromptTemplateJsonField error={messagesError}>
            <Textarea
              aria-label="Prompt Template JSON"
              value={messages}
              onChange={(event) => {
                setMessagesError(null);
                setMessages(event.target.value);
              }}
            />
          </PromptTemplateJsonField>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={isSystem} onChange={(event) => setIsSystem(event.target.checked)} />
            System prompt
          </label>
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
            <h3 className="text-base font-semibold text-slate-950">{prompt.name}</h3>
            <p className="mt-1 text-sm text-slate-600">{prompt.description ?? "No description"}</p>
            <p className="mt-2 text-xs text-slate-500">
              Owner {prompt.owner_id ?? "none"} · {prompt.is_system ? "System" : "User"} prompt
            </p>
          </div>
          <Button type="button" variant="secondary" onClick={() => onEdit(prompt.id)}>
            Edit
          </Button>
        </div>
      )}
    </Card>
  );
}

function PromptTemplateJsonField({
  children,
  error
}: {
  children: ReactNode;
  error?: string | null;
}) {
  return (
    <Field label="Prompt Template JSON">
      <div className="grid gap-2">
        <pre className="overflow-x-auto rounded-lg bg-slate-100 p-3 text-xs text-slate-700">
          {PROMPT_TEMPLATE_EXAMPLE}
        </pre>
        <p className="text-xs text-slate-500">Accepted keys: {PROMPT_TEMPLATE_KEYS.join(", ")}.</p>
        {children}
        {error ? <p className="text-sm text-red-700">{error}</p> : null}
      </div>
    </Field>
  );
}
