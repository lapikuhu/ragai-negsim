import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiClient, apiFetch, unwrapResult } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import type { ApiComponents, CounterpartPersonaRead } from "@/api/types";

type CounterpartPersonaCreateRequest = ApiComponents["schemas"]["CounterpartPersonaCreateRequest"];
type CounterpartPersonaUpdateRequest = ApiComponents["schemas"]["CounterpartPersonaUpdateRequest"];

export const personaKeys = {
  all: ["personas"] as const
};

export async function listPersonas() {
  const result = await apiClient.GET("/counterpart-personas/", { params: { query: { skip: 0, limit: 50 } } });
  return unwrapResult<CounterpartPersonaRead[]>(result, "Unable to load personas");
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

async function createPersona(input: CounterpartPersonaCreateRequest) {
  return jsonRequest<CounterpartPersonaRead>(
    "/counterpart-personas/",
    {
      method: "POST",
      body: JSON.stringify(input)
    },
    "Unable to create persona"
  );
}

async function updatePersona(personaId: number, input: CounterpartPersonaUpdateRequest) {
  return jsonRequest<CounterpartPersonaRead>(
    `/counterpart-personas/${personaId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input)
    },
    "Unable to update persona"
  );
}

export function usePersonasQuery() {
  return useQuery({ queryKey: personaKeys.all, queryFn: listPersonas });
}

function useInvalidatePersonas() {
  const queryClient = useQueryClient();
  return async () => queryClient.invalidateQueries({ queryKey: personaKeys.all });
}

export function useCreatePersonaMutation() {
  const invalidate = useInvalidatePersonas();
  return useMutation({
    mutationFn: createPersona,
    onSuccess: async () => invalidate()
  });
}

export function useUpdatePersonaMutation(personaId: number) {
  const invalidate = useInvalidatePersonas();
  return useMutation({
    mutationFn: (input: CounterpartPersonaUpdateRequest) => updatePersona(personaId, input),
    onSuccess: async () => invalidate()
  });
}
