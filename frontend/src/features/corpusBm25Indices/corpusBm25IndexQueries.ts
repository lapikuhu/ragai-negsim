import { useQuery } from "@tanstack/react-query";

import { apiClient, unwrapResult } from "@/api/client";
import type { CorpusBm25IndexMetadata } from "@/api/types";

export const corpusBm25IndexKeys = {
  all: ["corpus-bm25-indices"] as const,
  list: (corpusId?: number) => ["corpus-bm25-indices", { corpusId }] as const,
};

export async function listCorpusBm25Indices(corpusId?: number) {
  const pageSize = 100;
  const indices: CorpusBm25IndexMetadata[] = [];
  for (let skip = 0; ; skip += pageSize) {
    const result = await apiClient.GET("/corpus-bm25-indices/", {
      params: {
        query: {
          skip,
          limit: pageSize,
          status: "built",
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

export function useCorpusBm25IndicesQuery(corpusId?: number) {
  return useQuery({
    queryKey: corpusBm25IndexKeys.list(corpusId),
    queryFn: () => listCorpusBm25Indices(corpusId),
    enabled: Number.isFinite(corpusId),
  });
}
