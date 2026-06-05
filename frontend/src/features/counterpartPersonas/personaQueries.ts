import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, unwrapResult } from "@/api/client";
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

async function createPersona(input: CounterpartPersonaCreateRequest) {
  const result = await apiClient.POST("/counterpart-personas/", { body: input });
  return unwrapResult<CounterpartPersonaRead>(result, "Unable to create persona");
}

async function updatePersona(personaId: number, input: CounterpartPersonaUpdateRequest) {
  const result = await apiClient.PATCH("/counterpart-personas/{persona_id}", {
    params: { path: { persona_id: personaId } },
    body: input
  });
  return unwrapResult<CounterpartPersonaRead>(result, "Unable to update persona");
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
