import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, unwrapResult } from "@/api/client";
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

async function createScenario(input: ScenarioCreateRequest) {
  const result = await apiClient.POST("/scenarios/", { body: input });
  return unwrapResult<ScenarioRead>(result, "Unable to create scenario");
}

async function updateScenario(scenarioId: number, input: ScenarioUpdateRequest) {
  const result = await apiClient.PATCH("/scenarios/{scenario_id}", {
    params: { path: { scenario_id: scenarioId } },
    body: input
  });
  return unwrapResult<ScenarioRead>(result, "Unable to update scenario");
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
