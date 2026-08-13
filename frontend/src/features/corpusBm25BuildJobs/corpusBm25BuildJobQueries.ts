import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, apiFetch } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import { corpusBm25IndexKeys } from "@/features/corpusBm25Indices/corpusBm25IndexQueries";
import type {
  CorpusBm25BuildJobQueueRequest,
  CorpusBm25BuildJobRead,
  CorpusChunkSetSummary,
} from "@/api/types";

export type { CorpusBm25BuildJobQueueRequest, CorpusBm25BuildJobRead, CorpusChunkSetSummary };

export const corpusBm25BuildJobKeys = {
  all: ["corpus-bm25-build-jobs"] as const,
  list: (corpusId: number) => ["corpus-bm25-build-jobs", { corpusId }] as const,
  chunkSets: (corpusId: number) => ["corpora", corpusId, "chunk-sets"] as const,
};

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError("Unable to manage BM25 build", response.status, body);
  return body as T;
}

export function bm25JobRefetchInterval(data?: CorpusBm25BuildJobRead[]) {
  return data?.some((job) => job.status === "queued" || job.status === "running") ? 2000 : false;
}

export function useCorpusChunkSetsQuery(corpusId: number) {
  return useQuery({
    queryKey: corpusBm25BuildJobKeys.chunkSets(corpusId),
    queryFn: () => jsonRequest<CorpusChunkSetSummary[]>(`/corpora/${corpusId}/chunk-sets`),
    enabled: Number.isFinite(corpusId),
  });
}

export function useCorpusBm25BuildJobsQuery(corpusId: number) {
  const client = useQueryClient();
  const hadActiveJobs = useRef(false);
  const query = useQuery({
    queryKey: corpusBm25BuildJobKeys.list(corpusId),
    queryFn: () => jsonRequest<CorpusBm25BuildJobRead[]>(`/corpus-bm25-build-jobs/?skip=0&limit=100&corpus_id=${corpusId}`),
    enabled: Number.isFinite(corpusId),
    refetchInterval: (query) => bm25JobRefetchInterval(query.state.data),
  });
  const hasActiveJobs = bm25JobRefetchInterval(query.data) !== false;
  useEffect(() => {
    if (hadActiveJobs.current && !hasActiveJobs) {
      void client.invalidateQueries({ queryKey: corpusBm25IndexKeys.list(corpusId, null) });
    }
    hadActiveJobs.current = hasActiveJobs;
  }, [client, corpusId, hasActiveJobs]);
  return query;
}

function useInvalidate(corpusId: number) {
  const client = useQueryClient();
  return async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: corpusBm25BuildJobKeys.list(corpusId) }),
      client.invalidateQueries({ queryKey: corpusBm25IndexKeys.list(corpusId, null) }),
    ]);
  };
}

export function useQueueCorpusBm25BuildJobMutation(corpusId: number) {
  const invalidate = useInvalidate(corpusId);
  return useMutation({
    mutationFn: (input: CorpusBm25BuildJobQueueRequest) => jsonRequest<CorpusBm25BuildJobRead>("/corpus-bm25-build-jobs/", { method: "POST", body: JSON.stringify(input) }),
    onSuccess: invalidate,
  });
}

export function useCancelCorpusBm25BuildJobMutation(corpusId: number) {
  const invalidate = useInvalidate(corpusId);
  return useMutation({ mutationFn: (jobId: number) => jsonRequest<CorpusBm25BuildJobRead>(`/corpus-bm25-build-jobs/${jobId}/cancel`, { method: "POST" }), onSuccess: invalidate });
}

export function useRetryCorpusBm25BuildJobMutation(corpusId: number) {
  const invalidate = useInvalidate(corpusId);
  return useMutation({
    mutationFn: ({ jobId, requestedArtifactName }: { jobId: number; requestedArtifactName?: string }) => jsonRequest<CorpusBm25BuildJobRead>(`/corpus-bm25-build-jobs/${jobId}/retry`, { method: "POST", body: JSON.stringify(requestedArtifactName ? { requested_artifact_name: requestedArtifactName } : {}) }),
    onSuccess: invalidate,
  });
}
