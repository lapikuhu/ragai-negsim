import { useMemo, useState } from "react";
import type { VectorStoreRead } from "@/api/types";
import { getErrorMessage } from "@/api/client";
import {
  useCreateVectorStoreMutation,
  useDeleteVectorStoreMutation,
  useUpdateVectorStoreMutation,
  useVectorStoresQuery
} from "@/features/vectorStores/vectorStoreQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { VectorStoreForm } from "@/components/vectorStore/VectorStoreForm";
import { formatDateTime, stringifyJson } from "@/utils/format";

type ActiveAction =
  | { type: "edit"; vectorStoreId: number }
  | { type: "delete"; vectorStoreId: number }
  | null;

export function VectorStoresPage() {
  const query = useVectorStoresQuery();
  const createMutation = useCreateVectorStoreMutation();
  const [activeAction, setActiveAction] = useState<ActiveAction>(null);

  const activeStore = useMemo(
    () => query.data?.find((store) => store.id === activeAction?.vectorStoreId) ?? null,
    [activeAction?.vectorStoreId, query.data]
  );

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Vector Stores"
        description="Admin-managed vector store lifecycle controls using the existing backend CRUD API."
      />

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Create vector store</h2>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">
              Register a new vector store for indexing and retrieval workflows. All configuration is stored through the current backend API.
            </p>
          </div>
          <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
            <strong className="block text-slate-950">{query.data?.length ?? 0}</strong>
            configured store{(query.data?.length ?? 0) === 1 ? "" : "s"}
          </div>
        </div>

        <div className="mt-5">
          <VectorStoreForm
            submitLabel="Create vector store"
            submittingLabel="Creating..."
            successMessage="Vector store created."
            resetOnSuccess
            onSubmit={(input) => createMutation.mutateAsync(input)}
          />
        </div>
      </Card>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Stored vector stores</h2>
            <p className="mt-2 text-sm text-slate-600">
              Review backend type, linked corpus indices, and current connection details before editing or deleting a store.
            </p>
          </div>
        </div>

        {query.isLoading ? (
          <div className="mt-4">
            <LoadingState label="Loading vector stores..." />
          </div>
        ) : query.isError ? (
          <div className="mt-4">
            <ErrorState message={query.error.message} onRetry={() => query.refetch()} />
          </div>
        ) : query.data?.length ? (
          <div className="mt-4 grid gap-4">
            {query.data.map((store) => (
              <VectorStoreCard
                key={store.id}
                store={store}
                activeAction={
                  activeAction?.vectorStoreId === store.id
                    ? activeAction.type
                    : null
                }
                onActionChange={(type) => setActiveAction(type ? { type, vectorStoreId: store.id } : null)}
              />
            ))}
          </div>
        ) : (
          <div className="mt-4">
            <EmptyState title="No vector stores" description="Create the first vector store to enable admin-managed storage targets." />
          </div>
        )}

        {activeAction && !activeStore ? (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            The selected vector store is no longer available. Refresh the list and try again.
          </div>
        ) : null}
      </Card>
    </div>
  );
}

function VectorStoreCard({
  store,
  activeAction,
  onActionChange
}: {
  store: VectorStoreRead;
  activeAction: "edit" | "delete" | null;
  onActionChange: (type: "edit" | "delete" | null) => void;
}) {
  const linkedIndices = store.corpus_index_ids ?? [];
  const metadataJson = hasMetadata(store) ? stringifyJson(store.store_metadata) : null;

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="text-base font-semibold text-slate-950">{store.name}</h3>
            <span className="rounded-full bg-slate-200 px-2 py-1 text-xs font-medium text-slate-700">
              {store.backend}
            </span>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <SummaryItem label="Connection" value={summarizeConnection(store)} />
            <SummaryItem label="Collection / table" value={summarizeCollectionTarget(store)} />
            <SummaryItem label="Linked corpus indices" value={linkedIndices.length ? linkedIndices.join(", ") : "None"} />
            <SummaryItem label="Updated" value={formatDateTime(store.last_updated)} />
          </div>
          <div className="mt-3 grid gap-2 text-xs text-slate-500 md:grid-cols-2">
            <span>Created {formatDateTime(store.created_at)}</span>
            <span>Store ID #{store.id}</span>
          </div>
          {metadataJson ? (
            <div className="mt-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Metadata JSON</p>
              <pre className="mt-2 overflow-x-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100">{metadataJson}</pre>
            </div>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="secondary" onClick={() => onActionChange(activeAction === "edit" ? null : "edit")}>
            {activeAction === "edit" ? "Close" : "Edit"}
          </Button>
          <Button type="button" variant="danger" onClick={() => onActionChange(activeAction === "delete" ? null : "delete")}>
            {activeAction === "delete" ? "Close" : "Delete"}
          </Button>
        </div>
      </div>

      {activeAction === "edit" ? <EditVectorStorePanel store={store} onClose={() => onActionChange(null)} /> : null}
      {activeAction === "delete" ? <DeleteVectorStorePanel store={store} onClose={() => onActionChange(null)} /> : null}
    </div>
  );
}

function EditVectorStorePanel({ store, onClose }: { store: VectorStoreRead; onClose: () => void }) {
  const updateMutation = useUpdateVectorStoreMutation(store.id);

  return (
    <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
      <h3 className="text-base font-semibold text-slate-950">Edit vector store</h3>
      <p className="mt-2 text-sm text-slate-600">Update the stored configuration in place. Changes will refresh the shared vector store list.</p>
      <div className="mt-4">
        <VectorStoreForm
          initialValue={store}
          submitLabel="Save changes"
          submittingLabel="Saving..."
          successMessage="Vector store updated."
          onSubmit={(input) => updateMutation.mutateAsync(input)}
          onCancel={onClose}
          onSuccess={onClose}
        />
      </div>
    </div>
  );
}

function DeleteVectorStorePanel({ store, onClose }: { store: VectorStoreRead; onClose: () => void }) {
  const deleteMutation = useDeleteVectorStoreMutation(store.id);
  const [message, setMessage] = useState<string | null>(null);
  const linkedIndices = store.corpus_index_ids ?? [];

  return (
    <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-4">
      <h3 className="text-base font-semibold text-slate-950">Delete vector store</h3>
      <p className="mt-2 text-sm text-slate-600">
        Delete <strong>{store.name}</strong> only if you are sure it is no longer needed.
      </p>
      <p className="mt-2 text-xs text-slate-500">
        {linkedIndices.length
          ? `This store is currently linked to corpus indices: ${linkedIndices.join(", ")}. The backend may reject deletion until those links are removed.`
          : "This store has no linked corpus indices visible in the current response."}
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button
          type="button"
          variant="danger"
          disabled={deleteMutation.isPending}
          onClick={async () => {
            setMessage(null);
            try {
              await deleteMutation.mutateAsync();
              onClose();
            } catch (error) {
              setMessage(getErrorMessage(error, "Unable to delete vector store"));
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

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 break-words text-sm text-slate-700">{value}</p>
    </div>
  );
}

function summarizeConnection(store: VectorStoreRead) {
  return store.connection_uri || store.path || "No connection details stored";
}

function summarizeCollectionTarget(store: VectorStoreRead) {
  const parts = [store.collection_name, store.table_name].filter(Boolean);
  return parts.length ? parts.join(" / ") : "No collection or table stored";
}

function hasMetadata(store: VectorStoreRead) {
  return Boolean(store.store_metadata && Object.keys(store.store_metadata).length);
}