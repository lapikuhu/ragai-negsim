import { useState } from "react";
import { Link } from "react-router-dom";
import { useCorporaQuery, useCreateCorpusMutation } from "@/features/corpora/corpusQueries";
import {
  useChunkingProfilesQuery,
  useCorpusIndicesQuery,
  useVectorStoresQuery
} from "@/features/corpusIndices/corpusIndexQueries";
import { useDocumentsQuery } from "@/features/documents/documentQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { DataTable } from "@/components/common/DataTable";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/api/client";

export function CorporaPage() {
  const corpora = useCorporaQuery();
  const documents = useDocumentsQuery();
  const indices = useCorpusIndicesQuery();
  const profiles = useChunkingProfilesQuery();
  const vectorStores = useVectorStoresQuery();
  const createMutation = useCreateCorpusMutation();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [rawDocumentIds, setRawDocumentIds] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  return (
    <div className="grid gap-6">
      <PageHeader title="Corpora and RAG" description="Corpora, indices, vector stores, and chunking profiles grounded in the existing API." />

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Create corpus</h2>
        <form
          className="mt-4 grid gap-3 md:grid-cols-2"
          onSubmit={async (event) => {
            event.preventDefault();
            setMessage(null);
            try {
              await createMutation.mutateAsync({
                name,
                description: description || null,
                raw_document_ids: rawDocumentIds
                  .split(",")
                  .map((value) => value.trim())
                  .filter(Boolean)
                  .map(Number)
              });
              setName("");
              setDescription("");
              setRawDocumentIds("");
              setMessage("Corpus created.");
            } catch (error) {
              setMessage(getErrorMessage(error));
            }
          }}
        >
          <Field label="Name">
            <Input value={name} onChange={(event) => setName(event.target.value)} required />
          </Field>
          <Field
            label="Raw document IDs"
            hint={`Available raw documents: ${(documents.data ?? []).map((document) => document.id).join(", ") || "none"}`}
          >
            <Input
              value={rawDocumentIds}
              onChange={(event) => setRawDocumentIds(event.target.value)}
              placeholder="e.g. 1,2"
            />
          </Field>
          <Field label="Description" hint="Optional">
            <Textarea value={description} onChange={(event) => setDescription(event.target.value)} />
          </Field>
          <div className="flex items-end gap-3">
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating..." : "Create corpus"}
            </Button>
            {message ? <span className="text-sm text-slate-600">{message}</span> : null}
          </div>
        </form>
      </Card>

      {corpora.isLoading ? (
        <LoadingState label="Loading corpora..." />
      ) : corpora.isError ? (
        <ErrorState message={corpora.error.message} onRetry={() => corpora.refetch()} />
      ) : corpora.data?.length ? (
        <DataTable
          rows={corpora.data}
          columns={[
            {
              key: "name",
              header: "Corpus",
              render: (corpus) => (
                <div>
                  <Link className="font-medium text-accent" to={`/corpora/${corpus.id}`}>
                    {corpus.name}
                  </Link>
                  <p className="mt-1 text-xs text-slate-500">{corpus.description ?? "No description"}</p>
                </div>
              )
            },
            { key: "owner", header: "Created by", render: (corpus) => corpus.created_by_user_id },
            { key: "created", header: "Created", render: (corpus) => formatDateTime(corpus.created_at) }
          ]}
        />
      ) : (
        <EmptyState title="No corpora" description="Create a corpus to start ingestion and indexing workflows." />
      )}

      <div className="grid gap-4 xl:grid-cols-3">
        <Card>
          <h2 className="text-lg font-semibold text-slate-950">Chunking profiles</h2>
          <p className="mt-3 text-sm text-slate-600">{profiles.data?.length ?? 0} profiles available for chunk or ingest actions.</p>
        </Card>
        <Card>
          <h2 className="text-lg font-semibold text-slate-950">Vector stores</h2>
          <p className="mt-3 text-sm text-slate-600">{vectorStores.data?.length ?? 0} stores available for embedding jobs.</p>
        </Card>
        <Card>
          <h2 className="text-lg font-semibold text-slate-950">Corpus indices</h2>
          <p className="mt-3 text-sm text-slate-600">{indices.data?.length ?? 0} indices exposed by the backend.</p>
        </Card>
      </div>
    </div>
  );
}
