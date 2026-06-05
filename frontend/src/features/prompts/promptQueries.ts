import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, unwrapResult } from "@/api/client";
import type { ApiComponents, PromptRead } from "@/api/types";

type PromptCreate = ApiComponents["schemas"]["PromptCreate"];
type PromptAdminUpdate = ApiComponents["schemas"]["PromptAdminUpdate"];

export const promptKeys = {
  all: ["prompts"] as const
};

export async function listPrompts() {
  const result = await apiClient.GET("/prompts/", { params: { query: { skip: 0, limit: 50 } } });
  return unwrapResult<PromptRead[]>(result, "Unable to load prompts");
}

async function createPrompt(input: PromptCreate) {
  const result = await apiClient.POST("/prompts/", { body: input });
  return unwrapResult<PromptRead>(result, "Unable to create prompt");
}

async function updatePrompt(promptId: number, input: PromptAdminUpdate) {
  const result = await apiClient.PATCH("/prompts/{prompt_id}", {
    params: { path: { prompt_id: promptId } },
    body: input
  });
  return unwrapResult<PromptRead>(result, "Unable to update prompt");
}

export function usePromptsQuery() {
  return useQuery({ queryKey: promptKeys.all, queryFn: listPrompts });
}

function useInvalidatePrompts() {
  const queryClient = useQueryClient();
  return async () => queryClient.invalidateQueries({ queryKey: promptKeys.all });
}

export function useCreatePromptMutation() {
  const invalidate = useInvalidatePrompts();
  return useMutation({
    mutationFn: createPrompt,
    onSuccess: async () => invalidate()
  });
}

export function useUpdatePromptMutation(promptId: number) {
  const invalidate = useInvalidatePrompts();
  return useMutation({
    mutationFn: (input: PromptAdminUpdate) => updatePrompt(promptId, input),
    onSuccess: async () => invalidate()
  });
}
