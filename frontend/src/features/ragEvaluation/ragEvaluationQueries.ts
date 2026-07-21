import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { ApiError, apiClient, unwrapResult } from "@/api/client";
import type {
  RagEvalConfigurationInput,
  RagEvalConfigurationRead,
  RagEvalConfigurationUpdate,
  RagEvalRunDetailRead,
  RagEvalRunRead,
} from "./ragEvaluationTypes";

export const ragEvaluationKeys = {
  configurations: (skip = 0, limit = 20) =>
    ["rag-eval-configurations", { skip, limit }] as const,
  configuration: (id: number) => ["rag-eval-configuration", id] as const,
  latestRun: (configurationId: number) =>
    ["rag-eval-latest-run", configurationId] as const,
  history: (configurationId: number, skip: number, limit: number) =>
    ["rag-eval-run-history", configurationId, { skip, limit }] as const,
  run: (id: number) => ["rag-eval-run", id] as const,
};

const configurationListKey = ["rag-eval-configurations"] as const;
const historyKey = (configurationId: number) =>
  ["rag-eval-run-history", configurationId] as const;

export function getRagEvalRunRefetchInterval(
  run: Pick<RagEvalRunRead, "status" | "stage"> | null | undefined,
) {
  return run?.status === "queued" || run?.status === "running" ? 2000 : false;
}

function getRagEvalRunHistoryRefetchInterval(runs: RagEvalRunRead[] | undefined) {
  return runs?.some((run) => getRagEvalRunRefetchInterval(run) === 2000)
    ? 2000
    : false;
}

async function listConfigurations(skip: number, limit: number) {
  const result = await apiClient.GET("/rag-eval-configurations/", {
    params: { query: { skip, limit } },
  });
  return unwrapResult<RagEvalConfigurationRead[]>(
    result,
    "Unable to load RAG evaluation configurations",
  );
}

async function getConfiguration(id: number) {
  const result = await apiClient.GET("/rag-eval-configurations/{id}", {
    params: { path: { id } },
  });
  return unwrapResult<RagEvalConfigurationRead>(
    result,
    "Unable to load RAG evaluation configuration",
  );
}

async function listRuns(configurationId: number, skip: number, limit: number) {
  const result = await apiClient.GET("/rag-eval-runs/", {
    params: {
      query: { configuration_id: configurationId, skip, limit },
    },
  });
  return unwrapResult<RagEvalRunRead[]>(result, "Unable to load RAG evaluation runs");
}

async function getLatestRun(configurationId: number) {
  const runs = await listRuns(configurationId, 0, 1);
  return runs[0] ?? null;
}

async function getRun(runId: number) {
  const result = await apiClient.GET("/rag-eval-runs/{id}", {
    params: { path: { id: runId } },
  });
  return unwrapResult<RagEvalRunDetailRead>(result, "Unable to load RAG evaluation run");
}

async function createConfiguration(input: RagEvalConfigurationInput) {
  const result = await apiClient.POST("/rag-eval-configurations/", { body: input });
  return unwrapResult<RagEvalConfigurationRead>(
    result,
    "Unable to create RAG evaluation configuration",
  );
}

async function updateConfiguration({
  id,
  input,
}: {
  id: number;
  input: RagEvalConfigurationUpdate;
}) {
  const result = await apiClient.PATCH("/rag-eval-configurations/{id}", {
    params: { path: { id } },
    body: input,
  });
  return unwrapResult<RagEvalConfigurationRead>(
    result,
    "Unable to update RAG evaluation configuration",
  );
}

async function deleteConfiguration(id: number) {
  const result = await apiClient.DELETE("/rag-eval-configurations/{id}", {
    params: { path: { id } },
  });
  if (result.error) {
    throw new ApiError(
      "Unable to delete RAG evaluation configuration",
      result.response.status,
      result.error,
    );
  }
}

async function enqueueRun(configurationId: number) {
  const result = await apiClient.POST("/rag-eval-runs/", {
    body: { configuration_id: configurationId },
  });
  return unwrapResult<RagEvalRunRead>(result, "Unable to enqueue RAG evaluation run");
}

async function cancelRun(runId: number) {
  const result = await apiClient.POST("/rag-eval-runs/{id}/cancel", {
    params: { path: { id: runId } },
  });
  return unwrapResult<RagEvalRunRead>(result, "Unable to cancel RAG evaluation run");
}

export function useRagEvalConfigurationsQuery(skip: number, limit: number) {
  return useQuery({
    queryKey: ragEvaluationKeys.configurations(skip, limit),
    queryFn: () => listConfigurations(skip, limit),
  });
}

export function useRagEvalConfigurationQuery(id: number) {
  return useQuery({
    queryKey: ragEvaluationKeys.configuration(id),
    queryFn: () => getConfiguration(id),
  });
}

export function useLatestRagEvalRuns(configurationIds: number[]) {
  return useQueries({
    queries: configurationIds.map((configurationId) => ({
      queryKey: ragEvaluationKeys.latestRun(configurationId),
      queryFn: () => getLatestRun(configurationId),
      refetchInterval: (query: { state: { data?: RagEvalRunRead | null } }) =>
        getRagEvalRunRefetchInterval(query.state.data),
    })),
  });
}

export function useRagEvalRunHistoryQuery(
  configurationId: number | null,
  skip: number,
  limit: number,
) {
  return useQuery({
    queryKey:
      configurationId === null
        ? [...ragEvaluationKeys.history(0, skip, limit), "disabled"]
        : ragEvaluationKeys.history(configurationId, skip, limit),
    queryFn: () => listRuns(configurationId as number, skip, limit),
    enabled: configurationId !== null,
    refetchInterval: (query) => getRagEvalRunHistoryRefetchInterval(query.state.data),
  });
}

export function useRagEvalRunQuery(runId: number) {
  return useQuery({
    queryKey: ragEvaluationKeys.run(runId),
    queryFn: () => getRun(runId),
    refetchInterval: (query) => getRagEvalRunRefetchInterval(query.state.data),
  });
}

export function useCreateRagEvalConfigurationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createConfiguration,
    onSuccess: async (created) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: configurationListKey }),
        queryClient.invalidateQueries({
          queryKey: ragEvaluationKeys.configuration(created.id),
        }),
      ]);
    },
  });
}

export function useUpdateRagEvalConfigurationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateConfiguration,
    onSuccess: async (_updated, { id }) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: configurationListKey }),
        queryClient.invalidateQueries({ queryKey: ragEvaluationKeys.configuration(id) }),
      ]);
    },
  });
}

export function useDeleteRagEvalConfigurationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteConfiguration,
    onSuccess: async (_data, configurationId) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: configurationListKey }),
        queryClient.invalidateQueries({
          queryKey: ragEvaluationKeys.configuration(configurationId),
        }),
        queryClient.invalidateQueries({
          queryKey: ragEvaluationKeys.latestRun(configurationId),
        }),
        queryClient.invalidateQueries({ queryKey: historyKey(configurationId) }),
      ]);
    },
  });
}

export function useEnqueueRagEvalRunMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: enqueueRun,
    onSuccess: async (run, configurationId) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ragEvaluationKeys.latestRun(configurationId),
        }),
        queryClient.invalidateQueries({ queryKey: historyKey(configurationId) }),
        queryClient.invalidateQueries({ queryKey: ragEvaluationKeys.run(run.id) }),
      ]);
    },
  });
}

export function useCancelRagEvalRunMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cancelRun,
    onSuccess: async (run, runId) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ragEvaluationKeys.latestRun(run.configuration_id),
        }),
        queryClient.invalidateQueries({ queryKey: historyKey(run.configuration_id) }),
        queryClient.invalidateQueries({ queryKey: ragEvaluationKeys.run(runId) }),
      ]);
    },
  });
}
