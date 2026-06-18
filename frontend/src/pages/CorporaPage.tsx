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
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<number[]>([]);
  const [documentPickerOpen, setDocumentPickerOpen] = useState(false);
  const [documentSearch, setDocumentSearch] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const availableDocuments = documents.data ?? [];
  const normalizedDocumentSearch = documentSearch.trim().toLowerCase();
  const visibleDocuments = normalizedDocumentSearch
    ? availableDocuments.filter((document) => {
        const haystack = `${document.name} ${document.description ?? ""} ${document.id}`.toLowerCase();
        return haystack.includes(normalizedDocumentSearch);
      })
    : availableDocuments;
  const selectedDocuments = availableDocuments.filter((document) => selectedDocumentIds.includes(document.id));

  function toggleDocumentSelection(documentId: number) {
    setSelectedDocumentIds((current) =>
      current.includes(documentId) ? current.filter((id) => id !== documentId) : [...current, documentId]
    );
  }

  return (
    <div className="grid gap-6">
      <PageHeader title="Corpora" description="Corpora grounded in the existing API." />

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
                raw_document_ids: selectedDocumentIds
              });
              setName("");
              setDescription("");
              setSelectedDocumentIds([]);
              setDocumentSearch("");
              setDocumentPickerOpen(false);
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
            label="Raw documents"
            hint={
              selectedDocuments.length
                ? `${selectedDocuments.length} document${selectedDocuments.length === 1 ? "" : "s"} selected`
                : "Choose one or more uploaded raw documents to include in this corpus."
            }
          >
            <div className="grid gap-3">
              <Button
                type="button"
                variant="secondary"
                className="justify-between"
                onClick={() => setDocumentPickerOpen(true)}
              >
                <span>{selectedDocuments.length ? "Edit raw document selection" : "Select raw documents"}</span>
                <span className="text-xs text-slate-500">
                  {availableDocuments.length ? `${availableDocuments.length} available` : "No documents yet"}
                </span>
              </Button>
              {selectedDocuments.length ? (
                <div className="flex flex-wrap gap-2">
                  {selectedDocuments.map((document) => (
                    <button
                      key={document.id}
                      type="button"
                      className="inline-flex items-center gap-2 rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-xs text-teal-900"
                      onClick={() => toggleDocumentSelection(document.id)}
                    >
                      <span>#{document.id}</span>
                      <span>{document.name}</span>
                      <span className="text-teal-700">Remove</span>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
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

      {documentPickerOpen ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/45 p-4">
          <Card className="max-h-[85vh] w-full max-w-3xl overflow-hidden p-0">
            <div className="border-b border-slate-200 px-5 py-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold text-slate-950">Select raw documents</h3>
                  <p className="mt-1 text-sm text-slate-600">
                    Pick the uploaded documents you want included in this corpus.
                  </p>
                </div>
                <Button type="button" variant="ghost" onClick={() => setDocumentPickerOpen(false)}>
                  Close
                </Button>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto_auto]">
                <Input
                  value={documentSearch}
                  onChange={(event) => setDocumentSearch(event.target.value)}
                  placeholder="Search by name, description, or ID"
                />
                <Button
                  type="button"
                  variant="secondary"
                  disabled={!availableDocuments.length}
                  onClick={() => setSelectedDocumentIds(availableDocuments.map((document) => document.id))}
                >
                  Select all
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  disabled={!selectedDocumentIds.length}
                  onClick={() => setSelectedDocumentIds([])}
                >
                  Clear
                </Button>
              </div>
            </div>

            <div className="max-h-[50vh] overflow-y-auto px-5 py-4">
              {documents.isLoading ? (
                <LoadingState label="Loading raw documents..." />
              ) : documents.isError ? (
                <ErrorState message={documents.error.message} onRetry={() => documents.refetch()} />
              ) : visibleDocuments.length ? (
                <div className="grid gap-3">
                  {visibleDocuments.map((document) => {
                    const isSelected = selectedDocumentIds.includes(document.id);
                    return (
                      <label
                        key={document.id}
                        className={`flex cursor-pointer items-start gap-3 rounded-2xl border px-4 py-3 transition ${
                          isSelected
                            ? "border-teal-300 bg-teal-50/80"
                            : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                        }`}
                      >
                        <input
                          type="checkbox"
                          className="mt-1 h-4 w-4 rounded border-slate-300 text-accent focus:ring-teal-200"
                          checked={isSelected}
                          onChange={() => toggleDocumentSelection(document.id)}
                        />
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-medium text-slate-950">{document.name}</span>
                            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
                              ID {document.id}
                            </span>
                          </div>
                          <p className="mt-1 text-sm text-slate-600">
                            {document.description ?? "No description"}
                          </p>
                          <p className="mt-2 text-xs text-slate-500">
                            Uploaded {formatDateTime(document.uploaded_at)}
                          </p>
                        </div>
                      </label>
                    );
                  })}
                </div>
              ) : (
                <EmptyState
                  title={availableDocuments.length ? "No matching documents" : "No raw documents yet"}
                  description={
                    availableDocuments.length
                      ? "Try a different search term or clear the filter."
                      : "Upload raw documents first, then come back to link them into a corpus."
                  }
                />
              )}
            </div>

            <div className="flex items-center justify-between border-t border-slate-200 px-5 py-4">
              <p className="text-sm text-slate-600">
                {selectedDocumentIds.length} document{selectedDocumentIds.length === 1 ? "" : "s"} selected
              </p>
              <div className="flex items-center gap-3">
                <Button type="button" variant="secondary" onClick={() => setDocumentPickerOpen(false)}>
                  Done
                </Button>
              </div>
            </div>
          </Card>
        </div>
      ) : null}

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
