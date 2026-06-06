import { useMemo, useState } from "react";
import type { ApiComponents, ChunkingProfileRead } from "@/api/types";
import { getErrorMessage } from "@/api/client";
import {
  useChunkingProfilesQuery,
  useCreateChunkingProfileMutation,
  useCopyChunkingProfileMutation,
  useDeleteChunkingProfileMutation,
  useUpdateChunkingProfileMutation
} from "@/features/chunkingProfiles/chunkingProfileQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { DataTable } from "@/components/common/DataTable";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { formatDateTime, parseJsonInput, stringifyJson } from "@/utils/format";

type ProfileFormState = {
  name: string;
  strategy: string;
  config: string;
};

type ActiveAction =
  | { type: "edit"; profileId: number }
  | { type: "copy"; profileId: number }
  | { type: "delete"; profileId: number }
  | null;

const defaultCreateForm: ProfileFormState = {
  name: "",
  strategy: "recursive",
  config: "{\n  \"chunk_size\": 1000,\n  \"chunk_overlap\": 150\n}"
};

export function ChunkingProfilesPage() {
  const query = useChunkingProfilesQuery();
  const createMutation = useCreateChunkingProfileMutation();
  const [createForm, setCreateForm] = useState<ProfileFormState>(defaultCreateForm);
  const [message, setMessage] = useState<string | null>(null);
  const [activeAction, setActiveAction] = useState<ActiveAction>(null);

  const activeProfile = useMemo(
    () => query.data?.find((profile) => profile.id === activeAction?.profileId) ?? null,
    [activeAction?.profileId, query.data]
  );

  if (query.isLoading) {
    return <LoadingState label="Loading chunking profiles..." />;
  }

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => query.refetch()} />;
  }

  const profiles = query.data ?? [];

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Chunking Profiles"
        description="Admin-owned reusable chunking configurations for ingestion and corpus workflows."
      />

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Create chunking profile</h2>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">
              Define a reusable strategy and config once, then use the stored profile from document or corpus ingestion flows.
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
              await createMutation.mutateAsync({
                name: createForm.name.trim(),
                strategy: createForm.strategy.trim(),
                config: parseJsonInput<Record<string, unknown>>(createForm.config, {})
              });
              setCreateForm(defaultCreateForm);
              setMessage("Chunking profile created.");
            } catch (error) {
              setMessage(getErrorMessage(error, "Unable to create chunking profile"));
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
              <Input
                value={createForm.strategy}
                onChange={(event) => setCreateForm((current) => ({ ...current, strategy: event.target.value }))}
                required
              />
            </Field>
          </div>
          <Field label="Config JSON" hint="Stored exactly as sent to the backend. Valid JSON object required.">
            <Textarea
              className="min-h-40 font-mono text-sm"
              value={createForm.config}
              onChange={(event) => setCreateForm((current) => ({ ...current, config: event.target.value }))}
            />
          </Field>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating..." : "Create profile"}
            </Button>
            {message ? <span className="text-sm text-slate-600">{message}</span> : null}
          </div>
        </form>
      </Card>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Stored profiles</h2>
            <p className="mt-2 text-sm text-slate-600">
              Strategy and config become locked once a profile is referenced by chunks or corpus indices. Names remain editable.
            </p>
          </div>
        </div>

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
                  )
                },
                {
                  key: "strategy",
                  header: "Strategy",
                  render: (profile) => (
                    <div>
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
                        {profile.strategy}
                      </span>
                    </div>
                  )
                },
                {
                  key: "config",
                  header: "Config",
                  render: (profile) => (
                    <pre className="max-w-xl overflow-hidden whitespace-pre-wrap break-words rounded-xl bg-slate-50 p-3 text-xs text-slate-700">
                      {stringifyJson(profile.config)}
                    </pre>
                  )
                },
                {
                  key: "references",
                  header: "References",
                  render: (profile) => (
                    <div className="text-sm">
                      <div className="font-medium text-slate-950">
                        {hasReferences(profile) ? "In use" : "Unused"}
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        {profile.document_chunk_ids?.length ?? 0} chunk{profile.document_chunk_ids?.length === 1 ? "" : "s"} ·{" "}
                        {profile.corpus_index_ids?.length ?? 0} index{profile.corpus_index_ids?.length === 1 ? "" : "es"}
                      </p>
                      {hasReferences(profile) ? (
                        <p className="mt-1 text-xs text-amber-700">Strategy/config locked by backend while referenced.</p>
                      ) : null}
                    </div>
                  )
                },
                {
                  key: "updated",
                  header: "Last updated",
                  render: (profile) => <span className="text-sm text-slate-600">{formatDateTime(profile.last_updated)}</span>
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
                        disabled={hasReferences(profile)}
                        onClick={() => setActiveAction({ type: "delete", profileId: profile.id })}
                      >
                        Delete
                      </Button>
                    </div>
                  )
                }
              ]}
            />

            {activeAction && activeProfile ? (
              <ActionPanel key={`${activeAction.type}-${activeProfile.id}`} action={activeAction} profile={activeProfile} onClose={() => setActiveAction(null)} />
            ) : null}
          </div>
        ) : (
          <div className="mt-4">
            <EmptyState
              title="No chunking profiles"
              description="Create the first reusable chunking profile here, then select it during ingestion."
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
  onClose
}: {
  action: Exclude<ActiveAction, null>;
  profile: ChunkingProfileRead;
  onClose: () => void;
}) {
  if (action.type === "edit") {
    return <EditProfilePanel profile={profile} onClose={onClose} />;
  }

  if (action.type === "copy") {
    return <CopyProfilePanel profile={profile} onClose={onClose} />;
  }

  return <DeleteProfilePanel profile={profile} onClose={onClose} />;
}

function EditProfilePanel({ profile, onClose }: { profile: ChunkingProfileRead; onClose: () => void }) {
  const updateMutation = useUpdateChunkingProfileMutation(profile.id);
  const [form, setForm] = useState<ProfileFormState>({
    name: profile.name,
    strategy: profile.strategy,
    config: stringifyJson(profile.config)
  });
  const [message, setMessage] = useState<string | null>(null);
  const referenced = hasReferences(profile);

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <h3 className="text-base font-semibold text-slate-950">Edit profile</h3>
      <p className="mt-2 text-sm text-slate-600">
        {referenced
          ? "This profile is already referenced. You can rename it, but strategy and config are locked by backend rules."
          : "Update the stored profile fields in place."}
      </p>
      <form
        className="mt-4 grid gap-3"
        onSubmit={async (event) => {
          event.preventDefault();
          setMessage(null);
          try {
            await updateMutation.mutateAsync({
              name: form.name.trim(),
              strategy: referenced ? undefined : form.strategy.trim(),
              config: referenced ? undefined : parseJsonInput<Record<string, unknown>>(form.config, {})
            });
            onClose();
          } catch (error) {
            setMessage(getErrorMessage(error, "Unable to update chunking profile"));
          }
        }}
      >
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Name">
            <Input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} required />
          </Field>
          <Field label="Strategy">
            <Input
              value={form.strategy}
              onChange={(event) => setForm((current) => ({ ...current, strategy: event.target.value }))}
              disabled={referenced}
              required
            />
          </Field>
        </div>
        <Field label="Config JSON">
          <Textarea
            className="min-h-40 font-mono text-sm"
            value={form.config}
            onChange={(event) => setForm((current) => ({ ...current, config: event.target.value }))}
            disabled={referenced}
          />
        </Field>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={updateMutation.isPending}>
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

function CopyProfilePanel({ profile, onClose }: { profile: ChunkingProfileRead; onClose: () => void }) {
  const copyMutation = useCopyChunkingProfileMutation(profile.id);
  const [form, setForm] = useState<ProfileFormState>({
    name: `${profile.name} Copy`,
    strategy: profile.strategy,
    config: stringifyJson(profile.config)
  });
  const [message, setMessage] = useState<string | null>(null);

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <h3 className="text-base font-semibold text-slate-950">Copy profile</h3>
      <p className="mt-2 text-sm text-slate-600">
        Start from the selected profile and store a new variant with a different name, strategy, or config.
      </p>
      <form
        className="mt-4 grid gap-3"
        onSubmit={async (event) => {
          event.preventDefault();
          setMessage(null);
          try {
            await copyMutation.mutateAsync({
              name: form.name.trim(),
              strategy: form.strategy.trim(),
              config: parseJsonInput<Record<string, unknown>>(form.config, {})
            });
            onClose();
          } catch (error) {
            setMessage(getErrorMessage(error, "Unable to copy chunking profile"));
          }
        }}
      >
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="New name">
            <Input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} required />
          </Field>
          <Field label="Strategy">
            <Input
              value={form.strategy}
              onChange={(event) => setForm((current) => ({ ...current, strategy: event.target.value }))}
              required
            />
          </Field>
        </div>
        <Field label="Config JSON">
          <Textarea
            className="min-h-40 font-mono text-sm"
            value={form.config}
            onChange={(event) => setForm((current) => ({ ...current, config: event.target.value }))}
          />
        </Field>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={copyMutation.isPending}>
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

function DeleteProfilePanel({ profile, onClose }: { profile: ChunkingProfileRead; onClose: () => void }) {
  const deleteMutation = useDeleteChunkingProfileMutation(profile.id);
  const [message, setMessage] = useState<string | null>(null);

  return (
    <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4">
      <h3 className="text-base font-semibold text-slate-950">Delete profile</h3>
      <p className="mt-2 text-sm text-slate-600">
        Delete <strong>{profile.name}</strong> only if you are sure it is no longer needed.
      </p>
      <p className="mt-2 text-xs text-slate-500">
        This action is only available when the profile has no linked chunks or corpus indices.
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
              setMessage(getErrorMessage(error, "Unable to delete chunking profile"));
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

function hasReferences(profile: ChunkingProfileRead) {
  return Boolean((profile.document_chunk_ids?.length ?? 0) || (profile.corpus_index_ids?.length ?? 0));
}
