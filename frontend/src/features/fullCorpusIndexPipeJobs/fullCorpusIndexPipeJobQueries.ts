import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiClient, apiFetch, unwrapResult } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import type {
  ApiComponents,
  FullCorpusIndexPipeJobCreate,
  FullCorpusIndexPipeJobDetail,
  FullCorpusIndexPipeJobQueued
} from "@/api/types";

type FullCorpusIndexPipeJobListItem = ApiComponents["schemas"]["FullCorpusIndexPipeJobQueued"];

export const fullCorpusIndexPipeJobKeys = {
  all: ["full-corpus-index-pipe-jobs"] as const,
  active: ["full-corpus-index-pipe-jobs", "active"] as const,
  detail: (jobId: number) => ["full-corpus-index-pipe-jobs", jobId] as const
};

async function jsonRequest<T>(path: string, init: RequestInit, fallback: string) {
  const response = await apiFetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {})
    }
  });
  const detail = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(fallback, response.status, detail);
  }
  return detail as T;
}

async function createFullCorpusIndexPipeJob(input: FullCorpusIndexPipeJobCreate) {
  return jsonRequest<FullCorpusIndexPipeJobQueued>(
    "/full-corpus-index-pipe-jobs/",
    {
      method: "POST",
      body: JSON.stringify(input)
    },
    "Unable to queue full corpus index pipe job"
  );
}

async function cancelFullCorpusIndexPipeJob(jobId: number) {
  return jsonRequest<FullCorpusIndexPipeJobDetail>(
    `/full-corpus-index-pipe-jobs/${jobId}/cancel`,
    {
      method: "POST"
    },
    "Unable to cancel full corpus index pipe job"
  );
}

async function listFullCorpusIndexPipeJobs() {
  const result = await apiClient.GET("/full-corpus-index-pipe-jobs/", {
    params: { query: { skip: 0, limit: 50 } }
  });
  return unwrapResult<FullCorpusIndexPipeJobListItem[]>(result, "Unable to load full corpus index pipe jobs");
}

async function getActiveFullCorpusIndexPipeJob() {
  const result = await apiClient.GET("/full-corpus-index-pipe-jobs/active");
  if (result.response.status === 204) {
    return null;
  }
  return unwrapResult<FullCorpusIndexPipeJobDetail>(result, "Unable to load active full corpus index pipe job");
}

async function getFullCorpusIndexPipeJobDetail(jobId: number) {
  const result = await apiClient.GET("/full-corpus-index-pipe-jobs/{job_id}", {
    params: { path: { job_id: jobId } }
  });
  return unwrapResult<FullCorpusIndexPipeJobDetail>(result, "Unable to load full corpus index pipe job detail");
}

function useInvalidateFullCorpusIndexPipeJobs() {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: fullCorpusIndexPipeJobKeys.all }),
      queryClient.invalidateQueries({ queryKey: fullCorpusIndexPipeJobKeys.active }),
      queryClient.invalidateQueries({ queryKey: ["corpus-indices"] })
    ]);
  };
}

export function useCreateFullCorpusIndexPipeJobMutation() {
  const invalidate = useInvalidateFullCorpusIndexPipeJobs();
  return useMutation({
    mutationFn: createFullCorpusIndexPipeJob,
    onSuccess: async () => invalidate()
  });
}

export function useCancelFullCorpusIndexPipeJobMutation() {
  const invalidate = useInvalidateFullCorpusIndexPipeJobs();
  return useMutation({
    mutationFn: cancelFullCorpusIndexPipeJob,
    onSuccess: async () => invalidate()
  });
}

export function useFullCorpusIndexPipeJobsQuery(isActivePolling: boolean) {
  return useQuery({
    queryKey: fullCorpusIndexPipeJobKeys.all,
    queryFn: listFullCorpusIndexPipeJobs,
    refetchInterval: isActivePolling ? 2000 : false
  });
}

export function useActiveFullCorpusIndexPipeJobQuery() {
  return useQuery({
    queryKey: fullCorpusIndexPipeJobKeys.active,
    queryFn: getActiveFullCorpusIndexPipeJob,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 2000 : false;
    }
  });
}

export function useFullCorpusIndexPipeJobDetailQuery(jobId: number | null) {
  return useQuery({
    queryKey: jobId ? fullCorpusIndexPipeJobKeys.detail(jobId) : [...fullCorpusIndexPipeJobKeys.detail(0), "disabled"],
    queryFn: () => getFullCorpusIndexPipeJobDetail(jobId as number),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 2000 : false;
    }
  });
}
