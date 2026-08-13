import { useQuery } from "@tanstack/react-query";

import { apiClient, unwrapResult } from "@/api/client";
import type { CorpusBm25IndexMetadata } from "@/api/types";

export const corpusBm25IndexKeys = {
  all: ["corpus-bm25-indices"] as const,
  list: (corpusId?: number, status: string | null = "built") => ["corpus-bm25-indices", { corpusId, status }] as const,
};

export type CorpusBm25IndexListOptions = { status?: string | null };

export async function listCorpusBm25Indices(corpusId?: number, options: CorpusBm25IndexListOptions = {}) {
  const status = options.status === undefined ? "built" : options.status;
  const pageSize = 100;
  const indices: CorpusBm25IndexMetadata[] = [];
  for (let skip = 0; ; skip += pageSize) {
    const result = await apiClient.GET("/corpus-bm25-indices/", {
      params: {
        query: {
          skip,
          limit: pageSize,
          ...(status === null ? {} : { status }),
          ...(corpusId ? { corpus_id: corpusId } : {}),
        },
      },
    });
    const page = unwrapResult<CorpusBm25IndexMetadata[]>(result, "Unable to load BM25 indices");
    indices.push(...page);
    if (page.length < pageSize) {
      return indices;
    }
  }
}

export function useCorpusBm25IndicesQuery(corpusId?: number, options: CorpusBm25IndexListOptions = {}) {
  const status = options.status === undefined ? "built" : options.status;
  return useQuery({
    queryKey: corpusBm25IndexKeys.list(corpusId, status),
    queryFn: () => listCorpusBm25Indices(corpusId, { status }),
    enabled: Number.isFinite(corpusId),
  });
}
