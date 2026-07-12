import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import type {
  KnowledgeGraphBuildJobRead,
  KnowledgeGraphIndexCreate,
  KnowledgeGraphIndexRead,
} from "@/api/types";

export const knowledgeGraphKeys = {
  all: ["knowledge-graph-indexes"] as const,
  jobs: ["knowledge-graph-build-jobs"] as const,
};

export function getKnowledgeGraphRefetchInterval(
  graphs: Array<{ active_job_id?: number | null; status: string }>,
) {
  const hasActiveJob = graphs.some(
    (graph) => Boolean(graph.active_job_id) || graph.status === "building",
  );
  return hasActiveJob ? 2000 : false;
}

function getKnowledgeGraphBuildJobRefetchInterval(
  jobs: KnowledgeGraphBuildJobRead[],
) {
  return jobs.some((job) => job.status === "queued" || job.status === "running")
    ? 2000
    : false;
}

async function jsonRequest<T>(path: string, init: RequestInit, fallback: string) {
  const response = await apiFetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  const detail = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(fallback, response.status, detail);
  }
  return detail as T;
}

export async function listKnowledgeGraphs() {
  return jsonRequest<KnowledgeGraphIndexRead[]>(
    "/knowledge-graph-indexes/?skip=0&limit=100",
    { method: "GET" },
    "Unable to load knowledge graphs",
  );
}

export async function listKnowledgeGraphBuildJobs() {
  return jsonRequest<KnowledgeGraphBuildJobRead[]>(
    "/knowledge-graph-build-jobs/?skip=0&limit=100",
    { method: "GET" },
    "Unable to load knowledge graph build jobs",
  );
}

async function createKnowledgeGraph(input: KnowledgeGraphIndexCreate) {
  return jsonRequest<KnowledgeGraphIndexRead>(
    "/knowledge-graph-indexes/",
    { method: "POST", body: JSON.stringify(input) },
    "Unable to create knowledge graph",
  );
}

async function buildKnowledgeGraph(graphId: number, rebuild: boolean) {
  return jsonRequest<KnowledgeGraphBuildJobRead>(
    `/knowledge-graph-indexes/${graphId}/${rebuild ? "rebuild" : "build"}`,
    { method: "POST" },
    "Unable to queue knowledge graph build",
  );
}

async function deleteKnowledgeGraph(graphId: number) {
  await jsonRequest<null>(
    `/knowledge-graph-indexes/${graphId}`,
    { method: "DELETE" },
    "Unable to delete knowledge graph",
  );
}

export function useKnowledgeGraphsQuery() {
  return useQuery({
    queryKey: knowledgeGraphKeys.all,
    queryFn: listKnowledgeGraphs,
    refetchInterval: (query) =>
      getKnowledgeGraphRefetchInterval(query.state.data ?? []),
  });
}

export function useKnowledgeGraphBuildJobsQuery() {
  return useQuery({
    queryKey: knowledgeGraphKeys.jobs,
    queryFn: listKnowledgeGraphBuildJobs,
    refetchInterval: (query) =>
      getKnowledgeGraphBuildJobRefetchInterval(query.state.data ?? []),
  });
}

function useInvalidateKnowledgeGraphs() {
  const client = useQueryClient();
  return async () => {
    await client.invalidateQueries({ queryKey: knowledgeGraphKeys.all });
    await client.invalidateQueries({ queryKey: knowledgeGraphKeys.jobs });
  };
}

export function useCreateKnowledgeGraphMutation() {
  const invalidate = useInvalidateKnowledgeGraphs();
  return useMutation({
    mutationFn: createKnowledgeGraph,
    onSuccess: invalidate,
  });
}

export function useBuildKnowledgeGraphMutation() {
  const invalidate = useInvalidateKnowledgeGraphs();
  return useMutation({
    mutationFn: ({ graphId, rebuild }: { graphId: number; rebuild: boolean }) =>
      buildKnowledgeGraph(graphId, rebuild),
    onSuccess: invalidate,
  });
}

export function useDeleteKnowledgeGraphMutation() {
  const invalidate = useInvalidateKnowledgeGraphs();
  return useMutation({
    mutationFn: deleteKnowledgeGraph,
    onSuccess: invalidate,
  });
}
