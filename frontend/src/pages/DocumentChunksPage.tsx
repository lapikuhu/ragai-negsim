import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { DataTable } from "@/components/common/DataTable";
import { PaginationControls } from "@/components/common/PaginationControls";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Card } from "@/components/ui/Card";
import { Field, Input, Select } from "@/components/ui/Field";
import { useDocumentChunksQuery, type DocumentChunkFilters } from "@/features/documentChunks/documentChunkQueries";
import { usePaginationParams } from "@/utils/pagination";
import { formatDateTime, stringifyJson } from "@/utils/format";
import { useSearchParams } from "react-router-dom";

function parseOptionalNumber(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function indexedStatusToFilter(value: string) {
  if (value === "true") {
    return true;
  }
  if (value === "false") {
    return false;
  }
  return undefined;
}

export function DocumentChunksPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const pagination = usePaginationParams();
  const documentId = searchParams.get("raw_document_id") ?? "";
  const profileId = searchParams.get("chunking_profile_id") ?? "";
  const indexedStatus = searchParams.get("has_indexed_chunks") ?? "all";

  const filters: DocumentChunkFilters = {
    skip: pagination.skip,
    limit: pagination.limit
  };
  const rawDocumentId = parseOptionalNumber(documentId);
  const chunkingProfileId = parseOptionalNumber(profileId);
  const hasIndexedChunks = indexedStatusToFilter(indexedStatus);
  if (rawDocumentId !== undefined) {
    filters.raw_document_id = rawDocumentId;
  }
  if (chunkingProfileId !== undefined) {
    filters.chunking_profile_id = chunkingProfileId;
  }
  if (hasIndexedChunks !== undefined) {
    filters.has_indexed_chunks = hasIndexedChunks;
  }
  const query = useDocumentChunksQuery(filters);

  const setFilterParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value && value !== "all") {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    next.set("page", "1");
    next.set("limit", String(pagination.limit));
    setSearchParams(next);
  };

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Document Chunks"
        description="Read-only admin inspection for persisted document chunks and their indexing references."
      />

      <Card>
        <div className="grid gap-3 md:grid-cols-3">
          <Field label="Document ID">
            <Input
              type="number"
              min={1}
              value={documentId}
              onChange={(event) => setFilterParam("raw_document_id", event.target.value)}
              placeholder="Any document"
            />
          </Field>
          <Field label="Chunking profile ID">
            <Input
              type="number"
              min={1}
              value={profileId}
              onChange={(event) => setFilterParam("chunking_profile_id", event.target.value)}
              placeholder="Any profile"
            />
          </Field>
          <Field label="Indexed status">
            <Select value={indexedStatus} onChange={(event) => setFilterParam("has_indexed_chunks", event.target.value)}>
              <option value="all">All chunks</option>
              <option value="true">Indexed only</option>
              <option value="false">Unindexed only</option>
            </Select>
          </Field>
        </div>
      </Card>

      {query.isLoading ? (
        <LoadingState label="Loading document chunks..." />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => query.refetch()} />
      ) : query.data?.items.length ? (
        <div>
          <DataTable
            rows={query.data.items}
            columns={[
            {
              key: "id",
              header: "Chunk",
              render: (chunk) => (
                <div>
                  <div className="font-medium text-slate-950">#{chunk.id}</div>
                  <p className="mt-1 text-xs text-slate-500">Index {chunk.chunk_index}</p>
                </div>
              )
            },
            {
              key: "document",
              header: "Document",
              render: (chunk) => (
                <div>
                  <div className="font-medium text-slate-950">{chunk.raw_document_name ?? `Document ${chunk.raw_document_id}`}</div>
                  <p className="mt-1 text-xs text-slate-500">ID {chunk.raw_document_id}</p>
                </div>
              )
            },
            {
              key: "profile",
              header: "Chunking profile",
              render: (chunk) => (
                <div>
                  <div className="font-medium text-slate-950">
                    {chunk.chunking_profile_name ?? `Profile ${chunk.chunking_profile_id}`}
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{chunk.chunking_strategy ?? "unknown"}</p>
                </div>
              )
            },
            {
              key: "indexed",
              header: "Indexed",
              render: (chunk) => (
                <div>
                  <StatusBadge status={chunk.is_indexed ? "indexed" : "unindexed"} />
                  <p className="mt-1 text-xs text-slate-500">
                    {chunk.indexed_count} indexed
                  </p>
                </div>
              )
            },
            {
              key: "job",
              header: "Job",
              render: (chunk) => chunk.indexing_job_id ?? "Manual"
            },
            {
              key: "metadata",
              header: "Metadata",
              render: (chunk) => (
                <pre className="max-w-sm overflow-hidden whitespace-pre-wrap break-words rounded-xl bg-slate-50 p-3 text-xs text-slate-700">
                  {stringifyJson(chunk.chunk_metadata)}
                </pre>
              )
            },
            {
              key: "created",
              header: "Created",
              render: (chunk) => formatDateTime(chunk.created_at)
            },
            {
              key: "updated",
              header: "Last updated",
              render: (chunk) => formatDateTime(chunk.last_updated)
            }
            ]}
          />
          {query.data.total > query.data.limit ? (
            <PaginationControls
              page={pagination.page}
              limit={query.data.limit}
              total={query.data.total}
              isBusy={query.isFetching}
              onPageChange={pagination.setPage}
            />
          ) : null}
        </div>
      ) : (
        <EmptyState
          title="No document chunks"
          description="Persisted chunks will appear here after ingestion or chunking workflows run."
        />
      )}
    </div>
  );
}
