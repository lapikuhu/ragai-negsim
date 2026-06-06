import { useState } from "react";
import { Link } from "react-router-dom";
import { useDocumentsQuery, useUploadDocumentMutation } from "@/features/documents/documentQueries";
import { useCorporaQuery } from "@/features/corpora/corpusQueries";
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

export function DocumentsPage() {
  const query = useDocumentsQuery();
  const corpora = useCorporaQuery();
  const uploadMutation = useUploadDocumentMutation();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [corpusIds, setCorpusIds] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  return (
    <div className="grid gap-6">
      <PageHeader title="Documents" description="Raw document upload and inspection using the multipart `/raw-documents/` route." />

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Upload PDF</h2>
        <form
          className="mt-4 grid gap-3 md:grid-cols-2"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!file) {
              setMessage("Choose a file first.");
              return;
            }
            const parsedCorpusIds = corpusIds
              .split(",")
              .map((value) => value.trim())
              .filter(Boolean);
            if (parsedCorpusIds.some((value) => !/^\d+$/.test(value))) {
              setMessage("Corpus IDs must be comma-separated integers.");
              return;
            }
            setMessage(null);
            try {
              await uploadMutation.mutateAsync({
                name,
                description,
                corpusIds: parsedCorpusIds.map(Number),
                file
              });
              setName("");
              setDescription("");
              setCorpusIds("");
              setFile(null);
              setMessage("Upload complete.");
            } catch (error) {
              setMessage(getErrorMessage(error));
            }
          }}
        >
          <Field label="Name">
            <Input value={name} onChange={(event) => setName(event.target.value)} required />
          </Field>
          <Field label="Linked corpus IDs" hint={`Available corpora: ${(corpora.data ?? []).map((corpus) => corpus.id).join(", ") || "none"}`}>
            <Input
              value={corpusIds}
              onChange={(event) => setCorpusIds(event.target.value)}
              placeholder="e.g. 1,2"
            />
          </Field>
          <Field label="Description">
            <Textarea value={description} onChange={(event) => setDescription(event.target.value)} />
          </Field>
          <Field label="PDF file">
            <Input type="file" accept="application/pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </Field>
          <div className="md:col-span-2 flex items-center gap-3">
            <Button type="submit" disabled={uploadMutation.isPending}>
              {uploadMutation.isPending ? "Uploading..." : "Upload document"}
            </Button>
            {message ? <span className="text-sm text-slate-600">{message}</span> : null}
          </div>
        </form>
      </Card>

      {query.isLoading ? (
        <LoadingState label="Loading documents..." />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => query.refetch()} />
      ) : query.data?.length ? (
        <DataTable
          rows={query.data}
          columns={[
            {
              key: "name",
              header: "Document",
              render: (document) => (
                <div>
                  <Link className="font-medium text-accent" to={`/documents/${document.id}`}>
                    {document.name}
                  </Link>
                  <p className="mt-1 text-xs text-slate-500">{document.description ?? "No description"}</p>
                </div>
              )
            },
            { key: "path", header: "Path", render: (document) => document.path },
            { key: "uploaded", header: "Uploaded", render: (document) => formatDateTime(document.uploaded_at) }
          ]}
        />
      ) : (
        <EmptyState title="No documents" description="Upload a PDF to seed document ingestion workflows." />
      )}
    </div>
  );
}
