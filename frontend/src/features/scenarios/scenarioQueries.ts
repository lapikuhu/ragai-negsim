import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiClient, apiFetch, unwrapResult } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import type { ApiComponents, ScenarioRead } from "@/api/types";

type ScenarioCreateRequest = ApiComponents["schemas"]["ScenarioCreateRequest"];
type ScenarioUpdateRequest = ApiComponents["schemas"]["ScenarioUpdateRequest"];

export const scenarioKeys = {
  all: ["scenarios"] as const
};

export async function listScenarios() {
  const result = await apiClient.GET("/scenarios/", { params: { query: { skip: 0, limit: 50 } } });
  return unwrapResult<ScenarioRead[]>(result, "Unable to load scenarios");
}

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

async function createScenario(input: ScenarioCreateRequest) {
  return jsonRequest<ScenarioRead>(
    "/scenarios/",
    {
      method: "POST",
      body: JSON.stringify(input)
    },
    "Unable to create scenario"
  );
}

async function updateScenario(scenarioId: number, input: ScenarioUpdateRequest) {
  return jsonRequest<ScenarioRead>(
    `/scenarios/${scenarioId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input)
    },
    "Unable to update scenario"
  );
}

export function useScenariosQuery() {
  return useQuery({ queryKey: scenarioKeys.all, queryFn: listScenarios });
}

function useInvalidateScenarios() {
  const queryClient = useQueryClient();
  return async () => queryClient.invalidateQueries({ queryKey: scenarioKeys.all });
}

export function useCreateScenarioMutation() {
  const invalidate = useInvalidateScenarios();
  return useMutation({
    mutationFn: createScenario,
    onSuccess: async () => invalidate()
  });
}

export function useUpdateScenarioMutation(scenarioId: number) {
  const invalidate = useInvalidateScenarios();
  return useMutation({
    mutationFn: (input: ScenarioUpdateRequest) => updateScenario(scenarioId, input),
    onSuccess: async () => invalidate()
  });
}
