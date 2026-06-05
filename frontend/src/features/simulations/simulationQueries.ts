import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, unwrapResult } from "@/api/client";
import type { ApiComponents, SimulationRead, SimulationReadWithState, SimulationTurnResponse } from "@/api/types";

type SimulationCreateRequest = ApiComponents["schemas"]["SimulationCreateRequest"];
type SimulationStartRequest = ApiComponents["schemas"]["SimulationStartRequest"];
type SimulationTurnRequest = ApiComponents["schemas"]["SimulationTurnRequest"];
type SimulationTeacherReviewRequest = ApiComponents["schemas"]["SimulationTeacherReviewRequest"];

export const simulationKeys = {
  all: ["simulations"] as const,
  detail: (simulationId: number) => ["simulations", simulationId] as const,
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

async function createSimulation(input: SimulationCreateRequest) {
  const result = await apiClient.POST("/simulations/", { body: input });
  return unwrapResult<SimulationRead>(result, "Unable to create simulation");
}

async function startSimulation(simulationId: number, input: SimulationStartRequest) {
  const result = await apiClient.POST("/simulations/{simulation_id}/start", {
    params: { path: { simulation_id: simulationId } },
    body: input
  });
  return unwrapResult<SimulationReadWithState>(result, "Unable to start simulation");
}

async function submitTurn(simulationId: number, input: SimulationTurnRequest) {
  const result = await apiClient.POST("/simulations/{simulation_id}/turn", {
    params: { path: { simulation_id: simulationId } },
    body: input
  });
  return unwrapResult<SimulationTurnResponse>(result, "Unable to submit turn");
}

async function reviewSimulation(simulationId: number, input: SimulationTeacherReviewRequest) {
  const result = await apiClient.POST("/simulations/{simulation_id}/review", {
    params: { path: { simulation_id: simulationId } },
    body: input
  });
  return unwrapResult<SimulationRead>(result, "Unable to submit review");
}

export function useSimulationsQuery() {
  return useQuery({ queryKey: simulationKeys.all, queryFn: listSimulations });
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

export function useReviewSimulationMutation(simulationId: number) {
  const invalidate = useInvalidateSimulation();
  return useMutation({
    mutationFn: (input: SimulationTeacherReviewRequest) => reviewSimulation(simulationId, input),
    onSuccess: async () => invalidate(simulationId)
  });
}
