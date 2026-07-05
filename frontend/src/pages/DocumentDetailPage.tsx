import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  useChunkDocumentMutation,
  useDocumentDetailQuery,
  useIngestDocumentMutation
} from "@/features/documents/documentQueries";
import { useChunkingProfilesQuery } from "@/features/corpusIndices/corpusIndexQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { KeyValueList } from "@/components/common/KeyValueList";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Field, Select } from "@/components/ui/Field";
import { formatDateTime, stringifyJson } from "@/utils/format";
import { getErrorMessage } from "@/api/client";

export function DocumentDetailPage() {
  const documentId = Number(useParams().documentId);
  const query = useDocumentDetailQuery(documentId);
  const profiles = useChunkingProfilesQuery();
  const ingestMutation = useIngestDocumentMutation(documentId);
  const chunkMutation = useChunkDocumentMutation(documentId);
  const [profileId, setProfileId] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  if (query.isLoading) {
    return <LoadingState label="Loading document..." />;
  }

  if (query.isError || !query.data) {
    return <ErrorState message={query.error?.message ?? "Document not found"} onRetry={() => query.refetch()} />;
  }

  const document = query.data;
  const sourceReady = document.source_status === "available";

  return (
    <div className="grid gap-6">
      <PageHeader title={document.name} description={document.description ?? "Raw document detail"} />

      <Card>
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
