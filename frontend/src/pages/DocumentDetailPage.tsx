import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  useChunkDocumentMutation,
  useDocumentDetailQuery,
  useIngestDocumentMutation,
  useUpdateDocumentMutation
} from "@/features/documents/documentQueries";
import { useAuth } from "@/app/AuthProvider";
import { useChunkingProfilesQuery } from "@/features/corpusIndices/corpusIndexQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { KeyValueList } from "@/components/common/KeyValueList";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { formatDateTime, stringifyJson } from "@/utils/format";
import { getErrorMessage } from "@/api/client";

export function DocumentDetailPage() {
  const documentId = Number(useParams().documentId);
  const auth = useAuth();
  const query = useDocumentDetailQuery(documentId);
  const profiles = useChunkingProfilesQuery();
  const ingestMutation = useIngestDocumentMutation(documentId);
  const chunkMutation = useChunkDocumentMutation(documentId);
  const updateMutation = useUpdateDocumentMutation(documentId);
  const [profileId, setProfileId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [isEditingMetadata, setIsEditingMetadata] = useState(false);
  const [metadataMessage, setMetadataMessage] = useState<string | null>(null);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [metadataForm, setMetadataForm] = useState({
    name: "",
    description: "",
    documentTitle: "",
    documentAuthor: "",
    documentYear: ""
  });

  if (query.isLoading) {
    return <LoadingState label="Loading document..." />;
  }

  if (query.isError || !query.data) {
    return <ErrorState message={query.error?.message ?? "Document not found"} onRetry={() => query.refetch()} />;
  }

  const document = query.data;
  const sourceReady = document.source_status === "available";
  const canEditMetadata =
    auth.hasRole("admin") ||
    (auth.hasRole("teacher") && auth.user?.id === document.uploaded_by_user_id);

  const resetMetadataForm = () => {
    setMetadataForm({
      name: document.name,
      description: document.description ?? "",
      documentTitle: document.document_title ?? "",
      documentAuthor: document.document_author ?? "",
      documentYear: document.document_year === null || document.document_year === undefined ? "" : String(document.document_year)
    });
    setMetadataError(null);
  };

  return (
    <div className="grid gap-6">
      <PageHeader title={document.name} description={document.description ?? "Raw document detail"} />

      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-950">Metadata</h2>
          {canEditMetadata && !isEditingMetadata ? (
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                resetMetadataForm();
                setIsEditingMetadata(true);
                setMetadataMessage(null);
              }}
            >
              Edit metadata
            </Button>
          ) : null}
        </div>
        {metadataMessage ? <p className="mb-4 rounded-xl bg-teal-50 px-3 py-2 text-sm text-teal-900">{metadataMessage}</p> : null}
        <KeyValueList
          items={[
            { label: "Document title", value: document.document_title ?? "Not available" },
            { label: "Author", value: document.document_author ?? "Not available" },
            { label: "Document year", value: document.document_year ?? "Not available" },
            { label: "Source path", value: document.source_path },
            { label: "Source status", value: <StatusBadge status={document.source_status} /> },
            { label: "Source size", value: document.source_size ?? "Not available" },
            { label: "Source mtime", value: formatDateTime(document.source_mtime) },
            { label: "Uploaded by", value: document.uploaded_by_username ?? document.uploaded_by_user_id },
            { label: "Uploaded at", value: formatDateTime(document.uploaded_at) }
          ]}
        />
      </Card>

      {canEditMetadata && isEditingMetadata ? (
        <Card>
          <h2 className="text-lg font-semibold text-slate-950">Edit metadata</h2>
          <form
            className="mt-4 grid gap-3 md:grid-cols-2"
            onSubmit={async (event) => {
              event.preventDefault();
              const trimmedName = metadataForm.name.trim();
              const trimmedYear = metadataForm.documentYear.trim();

              if (!trimmedName) {
                setMetadataError("Name is required.");
                return;
              }
              if (trimmedYear && !/^-?\d+$/.test(trimmedYear)) {
                setMetadataError("Year must be an integer.");
                return;
              }

              setMetadataError(null);
              setMetadataMessage(null);
              try {
                await updateMutation.mutateAsync({
                  name: trimmedName,
                  description: metadataForm.description.trim() || null,
                  document_title: metadataForm.documentTitle.trim() || null,
                  document_author: metadataForm.documentAuthor.trim() || null,
                  document_year: trimmedYear ? Number(trimmedYear) : null
                });
                setIsEditingMetadata(false);
                setMetadataMessage("Metadata updated.");
              } catch (error) {
                setMetadataError(getErrorMessage(error));
              }
            }}
          >
            <Field label="Name-Alias">
              <Input
                value={metadataForm.name}
                onChange={(event) => setMetadataForm((current) => ({ ...current, name: event.target.value }))}
                required
              />
            </Field>
            <Field label="Title">
              <Input
                value={metadataForm.documentTitle}
                onChange={(event) => setMetadataForm((current) => ({ ...current, documentTitle: event.target.value }))}
              />
            </Field>
            <Field label="Author">
              <Input
                value={metadataForm.documentAuthor}
                onChange={(event) => setMetadataForm((current) => ({ ...current, documentAuthor: event.target.value }))}
              />
            </Field>
            <Field label="Year" error={metadataError === "Year must be an integer." ? metadataError : undefined}>
              <Input
                value={metadataForm.documentYear}
                onChange={(event) => setMetadataForm((current) => ({ ...current, documentYear: event.target.value }))}
              />
            </Field>
            <Field label="Description">
              <Textarea
                value={metadataForm.description}
                onChange={(event) => setMetadataForm((current) => ({ ...current, description: event.target.value }))}
              />
            </Field>
            <div className="flex flex-wrap items-end gap-3 md:col-span-2">
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? "Saving..." : "Save metadata"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setIsEditingMetadata(false);
                  setMetadataError(null);
                }}
              >
                Cancel
              </Button>
              {metadataError && metadataError !== "Year must be an integer." ? (
                <span className="text-sm text-red-700">{metadataError}</span>
              ) : null}
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Associated corpora</h2>
        {document.associated_corpora?.length ? (
          <ul className="mt-4 grid gap-3">
            {document.associated_corpora.map((corpus) => (
              <li key={corpus.id} className="rounded-xl bg-slate-50 px-3 py-2">
                <Link className="font-medium text-accent" to={`/corpora/${corpus.id}`}>
                  {corpus.name}
                </Link>
                <p className="mt-1 text-xs text-slate-500">ID {corpus.id}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-4 rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-600">No associated corpora</p>
        )}
      </Card>

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Ingestion actions</h2>
        {!sourceReady ? (
          <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">
            This document cannot be ingested or chunked while its source status is{" "}
            <code>{document.source_status}</code>.
            Restore or re-upload the stored file first.
          </p>
        ) : null}
        <div className="mt-4 grid gap-4 md:grid-cols-[minmax(0,280px)_1fr]">
          <Field label="Chunking profile">
            <Select value={profileId} onChange={(event) => setProfileId(event.target.value)}>
              <option value="">Select profile</option>
              {(profiles.data ?? []).map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </Select>
          </Field>
          <div className="flex flex-wrap items-end gap-3">
            <Button
              type="button"
              variant="secondary"
              disabled={!sourceReady || !profileId || ingestMutation.isPending}
              onClick={async () => {
                try {
                  const result = await ingestMutation.mutateAsync(Number(profileId));
                  setMessage(`Ingested document. Summary: ${stringifyJson(result)}`);
                } catch (error) {
                  setMessage(getErrorMessage(error));
                }
              }}
            >
              Ingest
            </Button>
            <Button
              type="button"
              disabled={!sourceReady || !profileId || chunkMutation.isPending}
              onClick={async () => {
                try {
                  const result = await chunkMutation.mutateAsync(Number(profileId));
                  setMessage(`Chunked document. Summary: ${stringifyJson(result)}`);
                } catch (error) {
                  setMessage(getErrorMessage(error));
                }
              }}
            >
              Chunk
            </Button>
          </div>
        </div>
        {message ? <pre className="mt-4 overflow-x-auto rounded-xl bg-slate-950 p-3 text-xs text-slate-100">{message}</pre> : null}
      </Card>
    </div>
  );
}
