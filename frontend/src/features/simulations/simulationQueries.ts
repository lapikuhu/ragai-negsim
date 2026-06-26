import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiClient, apiFetch, unwrapResult } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import type {
  ApiComponents,
  SimulationEvaluationListResponse,
  SimulationCreateRequest,
  SimulationLearnerAskRequest,
  SimulationLearnerAskResponse,
  SimulationProxyDisableResponse,
  SimulationProxyTurnRequest,
  SimulationProxyTurnResponse,
  SimulationRead,
  SimulationReadWithState,
  SimulationStartRequest,
  SimulationTurnResponse
} from "@/api/types";

type SimulationTurnRequest = ApiComponents["schemas"]["SimulationTurnRequest"];
type SimulationTeacherReviewRequest = ApiComponents["schemas"]["SimulationTeacherReviewRequest"];

export const simulationKeys = {
  all: ["simulations"] as const,
  completed: (skip: number, limit: number) => ["simulations", "completed", skip, limit] as const,
  detail: (simulationId: number) => ["simulations", simulationId] as const,
  reviewed: (skip: number, limit: number) => ["simulations", "reviewed", skip, limit] as const,
  state: (simulationId: number) => ["simulations", simulationId, "state"] as const
};

export async function listSimulations() {
  const result = await apiClient.GET("/simulations/", { params: { query: { skip: 0, limit: 50 } } });
  return unwrapResult<SimulationRead[]>(result, "Unable to load simulations");
}

export async function getSimulation(simulationId: number) {
  const result = await apiClient.GET("/simulations/{simulation_id}", {
    params: { path: { simulation_id: simulationId } }
  });
  return unwrapResult<SimulationReadWithState>(result, "Unable to load simulation");
}

export async function getSimulationState(simulationId: number) {
  const result = await apiClient.GET("/simulations/{simulation_id}/state", {
    params: { path: { simulation_id: simulationId } }
  });
  return unwrapResult<SimulationReadWithState>(result, "Unable to load simulation state");
}

async function listReviewedSimulations(skip: number, limit: number) {
  return jsonRequest<SimulationEvaluationListResponse>(
    `/simulations/reviews?skip=${skip}&limit=${limit}`,
    { method: "GET" },
    "Unable to load reviews"
  );
}

async function listCompletedSimulations(skip: number, limit: number) {
  return jsonRequest<SimulationEvaluationListResponse>(
    `/simulations/completed?skip=${skip}&limit=${limit}`,
    { method: "GET" },
    "Unable to load completed simulations"
  );
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

async function createSimulation(input: SimulationCreateRequest) {
  return jsonRequest<SimulationRead>(
    "/simulations/",
    {
      method: "POST",
      body: JSON.stringify(input)
    },
    "Unable to create simulation"
  );
}

async function startSimulation(simulationId: number, input: SimulationStartRequest) {
  return jsonRequest<SimulationReadWithState>(
    `/simulations/${simulationId}/start`,
    {
      method: "POST",
      body: JSON.stringify(input)
    },
    "Unable to start simulation"
  );
}

async function submitTurn(simulationId: number, input: SimulationTurnRequest) {
  return jsonRequest<SimulationTurnResponse>(
    `/simulations/${simulationId}/turn`,
    {
      method: "POST",
      body: JSON.stringify(input)
    },
    "Unable to submit turn"
  );
}

async function submitProxyTurn(simulationId: number, input: SimulationProxyTurnRequest) {
  return jsonRequest<SimulationProxyTurnResponse>(
    `/simulations/${simulationId}/proxy-turn`,
    {
      method: "POST",
      body: JSON.stringify(input)
    },
    "Unable to submit proxy turn"
  );
}

async function submitLearnerAsk(simulationId: number, input: SimulationLearnerAskRequest) {
  return jsonRequest<SimulationLearnerAskResponse>(
    `/simulations/${simulationId}/learner/ask`,
    {
      method: "POST",
      body: JSON.stringify(input)
    },
    "Unable to ask learning agent"
  );
}

async function disableProxy(simulationId: number) {
  return jsonRequest<SimulationProxyDisableResponse>(
    `/simulations/${simulationId}/proxy/disable`,
    {
      method: "POST",
      body: JSON.stringify({})
    },
    "Unable to disable proxy"
  );
}

async function reviewSimulation(simulationId: number, input: SimulationTeacherReviewRequest) {
  return jsonRequest<SimulationRead>(
    `/simulations/${simulationId}/review`,
    {
      method: "POST",
      body: JSON.stringify(input)
    },
    "Unable to submit review"
  );
}

async function updateReviewSimulation(simulationId: number, input: SimulationTeacherReviewRequest) {
  return jsonRequest<SimulationRead>(
    `/simulations/${simulationId}/review`,
    {
      method: "PATCH",
      body: JSON.stringify(input)
    },
    "Unable to update review"
  );
}

async function deleteReviewSimulation(simulationId: number) {
  await jsonRequest<null>(
    `/simulations/${simulationId}/review`,
    {
      method: "DELETE"
    },
    "Unable to delete review"
  );
}

export function useSimulationsQuery() {
  return useQuery({ queryKey: simulationKeys.all, queryFn: listSimulations });
}

export function useReviewedSimulationsQuery(skip: number, limit: number) {
  return useQuery({
    queryKey: simulationKeys.reviewed(skip, limit),
    queryFn: () => listReviewedSimulations(skip, limit)
  });
}

export function useCompletedSimulationsQuery(skip: number, limit: number) {
  return useQuery({
    queryKey: simulationKeys.completed(skip, limit),
    queryFn: () => listCompletedSimulations(skip, limit)
  });
}

export function useSimulationDetailQuery(simulationId: number) {
  return useQuery({
    queryKey: simulationKeys.detail(simulationId),
    queryFn: () => getSimulation(simulationId),
    enabled: Number.isFinite(simulationId)
  });
}

export function useSimulationStateQuery(simulationId: number) {
  return useQuery({
    queryKey: simulationKeys.state(simulationId),
    queryFn: () => getSimulationState(simulationId),
    enabled: Number.isFinite(simulationId)
  });
}

function useInvalidateSimulation() {
  const queryClient = useQueryClient();
  return async (simulationId?: number) => {
    await queryClient.invalidateQueries({ queryKey: simulationKeys.all });
    await queryClient.invalidateQueries({ queryKey: ["simulations", "completed"] });
    await queryClient.invalidateQueries({ queryKey: ["simulations", "reviewed"] });
    if (typeof simulationId === "number") {
      await queryClient.invalidateQueries({ queryKey: simulationKeys.detail(simulationId) });
      await queryClient.invalidateQueries({ queryKey: simulationKeys.state(simulationId) });
    }
  };
}

export function useCreateSimulationMutation() {
  const invalidate = useInvalidateSimulation();
  return useMutation({
    mutationFn: createSimulation,
    onSuccess: async (simulation) => invalidate(simulation.id)
  });
}

export function useStartSimulationMutation(simulationId: number) {
  const invalidate = useInvalidateSimulation();
  return useMutation({
    mutationFn: (input: SimulationStartRequest) => startSimulation(simulationId, input),
    onSuccess: async () => invalidate(simulationId)
  });
}

export function useSimulationTurnMutation(simulationId: number) {
  const invalidate = useInvalidateSimulation();
  return useMutation({
    mutationFn: (input: SimulationTurnRequest) => submitTurn(simulationId, input),
    onSuccess: async () => invalidate(simulationId)
  });
}

export function useSimulationProxyTurnMutation(simulationId: number) {
  const invalidate = useInvalidateSimulation();
  return useMutation({
    mutationFn: (input: SimulationProxyTurnRequest) => submitProxyTurn(simulationId, input),
    onSuccess: async () => invalidate(simulationId)
  });
}

export function useSimulationLearnerAskMutation(simulationId: number) {
  return useMutation({
    mutationFn: (input: SimulationLearnerAskRequest) => submitLearnerAsk(simulationId, input)
  });
}

export function useDisableSimulationProxyMutation(simulationId: number) {
  const invalidate = useInvalidateSimulation();
  return useMutation({
    mutationFn: () => disableProxy(simulationId),
    onSuccess: async () => invalidate(simulationId)
  });
}

export function useReviewSimulationMutation(simulationId: number) {
  const invalidate = useInvalidateSimulation();
  return useMutation({
    mutationFn: (input: SimulationTeacherReviewRequest) => reviewSimulation(simulationId, input),
    onSuccess: async () => invalidate(simulationId)
  });
}

export function useUpdateReviewSimulationMutation(simulationId: number) {
  const invalidate = useInvalidateSimulation();
  return useMutation({
    mutationFn: (input: SimulationTeacherReviewRequest) => updateReviewSimulation(simulationId, input),
    onSuccess: async () => invalidate(simulationId)
  });
}

export function useDeleteReviewSimulationMutation() {
  const invalidate = useInvalidateSimulation();
  return useMutation({
    mutationFn: (simulationId: number) => deleteReviewSimulation(simulationId),
    onSuccess: async (_data, simulationId) => invalidate(simulationId)
  });
}
