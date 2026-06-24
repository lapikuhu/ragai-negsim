import { useQuery } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import type { PaginatedResponse } from "@/utils/pagination";

export type DocumentChunkFilters = {
  skip?: number;
  limit?: number;
  raw_document_id?: number;
  chunking_profile_id?: number;
  has_indexed_chunks?: boolean;
};

export type DocumentChunkAdminRead = {
  id: number;
  raw_document_id: number;
  raw_document_name?: string | null;
  chunking_profile_id: number;
  chunking_profile_name?: string | null;
  chunking_strategy?: string | null;
  indexing_job_id?: number | null;
  chunk_index: number;
  content: string;
  chunk_metadata: Record<string, unknown>;
  corpus_index_ids: number[];
  indexed_count: number;
  is_indexed: boolean;
  created_at: string;
  last_updated: string;
};

export const documentChunkKeys = {
  all: ["document-chunks"] as const,
  list: (filters: DocumentChunkFilters) => ["document-chunks", filters] as const
};

function appendOptionalNumber(params: URLSearchParams, key: string, value: number | undefined) {
  if (typeof value === "number" && Number.isFinite(value)) {
    params.set(key, String(value));
  }
}

async function listDocumentChunks(filters: DocumentChunkFilters) {
  const params = new URLSearchParams({
    skip: String(filters.skip ?? 0),
    limit: String(filters.limit ?? 20)
  });
  appendOptionalNumber(params, "raw_document_id", filters.raw_document_id);
  appendOptionalNumber(params, "chunking_profile_id", filters.chunking_profile_id);
  if (typeof filters.has_indexed_chunks === "boolean") {
    params.set("has_indexed_chunks", String(filters.has_indexed_chunks));
  }

  const response = await apiFetch(`${getApiBaseUrl()}/document-chunks/?${params.toString()}`);
  const detail = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError("Unable to load document chunks", response.status, detail);
  }
  return detail as PaginatedResponse<DocumentChunkAdminRead>;
}

export function useDocumentChunksQuery(filters: DocumentChunkFilters) {
  return useQuery({
    queryKey: documentChunkKeys.list(filters),
    queryFn: () => listDocumentChunks(filters)
  });
}
