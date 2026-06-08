import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiClient, apiFetch, unwrapResult } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import type { ApiComponents, ScenarioAuthoringRead, ScenarioPublicRead } from "@/api/types";

type ScenarioCreateRequest = ApiComponents["schemas"]["ScenarioCreateRequest"];
type ScenarioUpdateRequest = ApiComponents["schemas"]["ScenarioUpdateRequest"];

export const scenarioKeys = {
  all: ["scenarios"] as const,
  authoring: (scenarioId: number) => ["scenarios", scenarioId, "authoring"] as const
};

export async function listScenarios() {
  const result = await apiClient.GET("/scenarios/", { params: { query: { skip: 0, limit: 50 } } });
  return unwrapResult<ScenarioPublicRead[]>(result, "Unable to load scenarios");
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
  return jsonRequest<ScenarioAuthoringRead>(
    "/scenarios/",
    {
      method: "POST",
      body: JSON.stringify(input)
    },
    "Unable to create scenario"
  );
}

async function getScenarioAuthoring(scenarioId: number) {
  return jsonRequest<ScenarioAuthoringRead>(
    `/scenarios/${scenarioId}/authoring`,
    { method: "GET" },
    "Unable to load scenario authoring data"
  );
}

async function updateScenario(scenarioId: number, input: ScenarioUpdateRequest) {
  return jsonRequest<ScenarioAuthoringRead>(
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

export function useScenarioAuthoringQuery(scenarioId: number, enabled: boolean) {
  return useQuery({
    queryKey: scenarioKeys.authoring(scenarioId),
    queryFn: () => getScenarioAuthoring(scenarioId),
    enabled
  });
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
