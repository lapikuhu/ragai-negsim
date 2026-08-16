import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, apiFetch } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import { corpusBm25IndexKeys } from "@/features/corpusBm25Indices/corpusBm25IndexQueries";
import type {
  CorpusBm25BuildJobQueueRequest,
  CorpusBm25BuildJobRead,
  CorpusChunkSetRead,
  CorpusChunkSetNameAvailability,
  CorpusBm25IndexNameAvailability,
} from "@/api/types";

export type { CorpusBm25BuildJobQueueRequest, CorpusBm25BuildJobRead, CorpusChunkSetRead };

export const corpusBm25BuildJobKeys = {
  all: ["corpus-bm25-build-jobs"] as const,
  list: (corpusId: number) => ["corpus-bm25-build-jobs", { corpusId }] as const,
  detail: (jobId: number) => ["corpus-bm25-build-jobs", "detail", jobId] as const,
  chunkSets: (corpusId: number) => ["corpora", corpusId, "chunk-sets"] as const,
  chunkSetNameAvailability: (corpusId: number, name: string) => ["corpora", corpusId, "chunk-set-name-availability", name] as const,
  nameAvailability: (name: string) => ["corpus-bm25-build-jobs", "name-availability", name] as const,
};

function useDebouncedValue(value: string, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [delay, value]);
  return debounced;
}

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
    queryFn: () => jsonRequest<CorpusChunkSetRead[]>(`/corpora/${corpusId}/chunk-sets`),
    enabled: Number.isFinite(corpusId),
  });
}

export function useCorpusChunkSetNameAvailabilityQuery(
  corpusId: number,
  name: string,
  enabled = true,
) {
  const normalized = useDebouncedValue(name.trim());
  return useQuery({
    queryKey: corpusBm25BuildJobKeys.chunkSetNameAvailability(corpusId, normalized),
    queryFn: ({ signal }) => jsonRequest<CorpusChunkSetNameAvailability>(
      `/corpora/${corpusId}/chunk-set-name-availability?name=${encodeURIComponent(normalized)}`,
      { signal },
    ),
    enabled: enabled && Number.isFinite(corpusId) && corpusId > 0 && normalized.length >= 3,
  });
}

export function useCorpusBm25NameAvailabilityQuery(name: string) {
  const normalized = useDebouncedValue(name.trim());
  return useQuery({
    queryKey: corpusBm25BuildJobKeys.nameAvailability(normalized),
    queryFn: () => jsonRequest<CorpusBm25IndexNameAvailability>(`/corpus-bm25-build-jobs/name-availability?name=${encodeURIComponent(normalized)}`),
    enabled: normalized.length >= 3,
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

export function useCorpusBm25BuildJobQuery(
  jobId: number | null,
  parentIsActive = false,
) {
  return useQuery({
    queryKey: corpusBm25BuildJobKeys.detail(jobId ?? 0),
    queryFn: () => jsonRequest<CorpusBm25BuildJobRead>(
      `/corpus-bm25-build-jobs/${jobId}`,
    ),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return parentIsActive || status === "queued" || status === "running"
        ? 2000
        : false;
    },
  });
}

function useInvalidate(corpusId: number) {
  const client = useQueryClient();
  return async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: corpusBm25BuildJobKeys.list(corpusId) }),
      client.invalidateQueries({ queryKey: corpusBm25IndexKeys.list(corpusId, null) }),
      client.invalidateQueries({ queryKey: corpusBm25BuildJobKeys.chunkSets(corpusId) }),
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
    mutationFn: ({ jobId, requestedArtifactName }: { jobId: number; requestedArtifactName: string }) => jsonRequest<CorpusBm25BuildJobRead>(`/corpus-bm25-build-jobs/${jobId}/retry`, { method: "POST", body: JSON.stringify({ requested_artifact_name: requestedArtifactName }) }),
    onSuccess: invalidate,
  });
}
