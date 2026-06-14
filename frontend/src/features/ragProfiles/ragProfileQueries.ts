import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import type {
  RagProfileCopy,
  RagProfileCreateRequest,
  RagProfileDefinitionRead,
  RagProfileRead,
  RagProfileUpdateRequest,
} from "@/api/types";

export const ragProfileKeys = {
  all: ["rag-profiles"] as const,
  definitions: ["rag-profile-definitions"] as const,
};

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

export async function listRagProfiles() {
  return jsonRequest<RagProfileRead[]>(
    "/rag-profiles/?skip=0&limit=50",
    { method: "GET" },
    "Unable to load RAG profiles",
  );
}

export async function listRagProfileDefinitions() {
  return jsonRequest<RagProfileDefinitionRead[]>(
    "/rag-profiles/definitions",
    { method: "GET" },
    "Unable to load RAG profile definitions",
  );
}

async function createRagProfile(input: RagProfileCreateRequest) {
  return jsonRequest<RagProfileRead>(
    "/rag-profiles/",
    {
      method: "POST",
      body: JSON.stringify(input),
    },
    "Unable to create RAG profile",
  );
}

async function updateRagProfile(profileId: number, input: RagProfileUpdateRequest) {
  return jsonRequest<RagProfileRead>(
    `/rag-profiles/${profileId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
    "Unable to update RAG profile",
  );
}

async function copyRagProfile(profileId: number, input: RagProfileCopy) {
  return jsonRequest<RagProfileRead>(
    `/rag-profiles/${profileId}/copy`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
    "Unable to copy RAG profile",
  );
}

async function deleteRagProfile(profileId: number) {
  await jsonRequest<null>(
    `/rag-profiles/${profileId}`,
    { method: "DELETE" },
    "Unable to delete RAG profile",
  );
}

export function useRagProfilesQuery() {
  return useQuery({ queryKey: ragProfileKeys.all, queryFn: listRagProfiles });
}

export function useRagProfileDefinitionsQuery() {
  return useQuery({ queryKey: ragProfileKeys.definitions, queryFn: listRagProfileDefinitions });
}

function useInvalidateRagProfiles() {
  const queryClient = useQueryClient();
  return async () => {
    await queryClient.invalidateQueries({ queryKey: ragProfileKeys.all });
  };
}

export function useCreateRagProfileMutation() {
  const invalidate = useInvalidateRagProfiles();
  return useMutation({
    mutationFn: createRagProfile,
    onSuccess: async () => invalidate(),
  });
}

export function useUpdateRagProfileMutation(profileId: number) {
  const invalidate = useInvalidateRagProfiles();
  return useMutation({
    mutationFn: (input: RagProfileUpdateRequest) => updateRagProfile(profileId, input),
    onSuccess: async () => invalidate(),
  });
}

export function useCopyRagProfileMutation(profileId: number) {
  const invalidate = useInvalidateRagProfiles();
  return useMutation({
    mutationFn: (input: RagProfileCopy) => copyRagProfile(profileId, input),
    onSuccess: async () => invalidate(),
  });
}

export function useDeleteRagProfileMutation(profileId: number) {
  const invalidate = useInvalidateRagProfiles();
  return useMutation({
    mutationFn: () => deleteRagProfile(profileId),
    onSuccess: async () => invalidate(),
  });
}
