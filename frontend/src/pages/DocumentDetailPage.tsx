import { useState } from "react";
import { useParams } from "react-router-dom";
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

  return (
    <div className="grid gap-6">
      <PageHeader title={document.name} description={document.description ?? "Raw document detail"} />

      <Card>
        <KeyValueList
          items={[
            { label: "Path", value: document.path },
            { label: "Uploaded by", value: document.uploaded_by_user_id },
            { label: "Uploaded at", value: formatDateTime(document.uploaded_at) },
            { label: "Parsed at", value: formatDateTime(document.parsed_at) }
          ]}
        />
      </Card>

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Ingestion actions</h2>
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
              disabled={!profileId || ingestMutation.isPending}
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
              disabled={!profileId || chunkMutation.isPending}
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
