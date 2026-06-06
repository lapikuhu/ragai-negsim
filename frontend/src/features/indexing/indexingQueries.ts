import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, unwrapResult } from "@/api/client";
import type {
  ApiComponents,
  IndexingJobCreate,
  IndexingJobDetail,
  IndexingJobQueued
} from "@/api/types";

type IndexingJobListItem = ApiComponents["schemas"]["IndexingJobQueued"];

export const indexingKeys = {
  all: ["indexing-jobs"] as const,
  active: ["indexing-jobs", "active"] as const,
  detail: (jobId: number) => ["indexing-jobs", jobId] as const
};

async function createIndexingJob(input: IndexingJobCreate) {
  const result = await apiClient.POST("/indexing-jobs/", { body: input });
  return unwrapResult<IndexingJobQueued>(result, "Unable to queue indexing job");
}

async function listIndexingJobs() {
  const result = await apiClient.GET("/indexing-jobs/", {
    params: { query: { skip: 0, limit: 50 } }
  });
  return unwrapResult<IndexingJobListItem[]>(result, "Unable to load indexing jobs");
}

async function getActiveIndexingJob() {
  const result = await apiClient.GET("/indexing-jobs/active");
  if (result.response.status === 204) {
    return null;
  }
  return unwrapResult<IndexingJobDetail>(result, "Unable to load active indexing job");
}

async function getIndexingJobDetail(jobId: number) {
  const result = await apiClient.GET("/indexing-jobs/{job_id}", {
    params: { path: { job_id: jobId } }
  });
  return unwrapResult<IndexingJobDetail>(result, "Unable to load indexing job detail");
}

function useInvalidateIndexing() {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: indexingKeys.all }),
      queryClient.invalidateQueries({ queryKey: indexingKeys.active }),
      queryClient.invalidateQueries({ queryKey: ["corpus-indices"] })
    ]);
  };
}

export function useCreateIndexingJobMutation() {
  const invalidate = useInvalidateIndexing();
  return useMutation({
    mutationFn: createIndexingJob,
    onSuccess: async () => invalidate()
  });
}

export function useIndexingJobsQuery() {
  return useQuery({ queryKey: indexingKeys.all, queryFn: listIndexingJobs });
}

export function useActiveIndexingJobQuery() {
  return useQuery({
    queryKey: indexingKeys.active,
    queryFn: getActiveIndexingJob,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 2000 : false;
    }
  });
}

export function useIndexingJobDetailQuery(jobId: number | null) {
  return useQuery({
    queryKey: jobId ? indexingKeys.detail(jobId) : [...indexingKeys.detail(0), "disabled"],
    queryFn: () => getIndexingJobDetail(jobId as number),
    enabled: jobId !== null
  });
}
