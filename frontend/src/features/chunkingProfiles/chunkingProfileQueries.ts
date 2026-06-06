import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiClient, apiFetch, unwrapResult } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import type { ApiComponents, ChunkerDefinitionRead, ChunkingProfileRead } from "@/api/types";

type ChunkingProfileCreate = ApiComponents["schemas"]["ChunkingProfileCreate"];
type ChunkingProfileUpdate = ApiComponents["schemas"]["ChunkingProfileUpdate"];
type ChunkingProfileCopy = ApiComponents["schemas"]["ChunkingProfileCopy"];

export const chunkingProfileKeys = {
  all: ["chunking-profiles"] as const,
  definitions: ["chunking-profile-definitions"] as const
};

export async function listChunkingProfiles() {
  const result = await apiClient.GET("/chunking-profiles/", { params: { query: { skip: 0, limit: 50 } } });
  return unwrapResult<ChunkingProfileRead[]>(result, "Unable to load chunking profiles");
}

export async function listChunkerDefinitions() {
  const response = await apiFetch(`${getApiBaseUrl()}/chunking-profiles/definitions`);
  const detail = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError("Unable to load chunker definitions", response.status, detail);
  }
  return detail as ChunkerDefinitionRead[];
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

async function createChunkingProfile(input: ChunkingProfileCreate) {
  return jsonRequest<ChunkingProfileRead>(
    "/chunking-profiles/",
    {
      method: "POST",
      body: JSON.stringify(input)
    },
    "Unable to create chunking profile"
  );
}

async function updateChunkingProfile(profileId: number, input: ChunkingProfileUpdate) {
  return jsonRequest<ChunkingProfileRead>(
    `/chunking-profiles/${profileId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input)
    },
    "Unable to update chunking profile"
  );
}

async function copyChunkingProfile(profileId: number, input: ChunkingProfileCopy) {
  return jsonRequest<ChunkingProfileRead>(
    `/chunking-profiles/${profileId}/copy`,
    {
      method: "POST",
      body: JSON.stringify(input)
    },
    "Unable to copy chunking profile"
  );
}

async function deleteChunkingProfile(profileId: number) {
  const result = await apiClient.DELETE("/chunking-profiles/{profile_id}", {
    params: { path: { profile_id: profileId } }
  });
  if (result.error) {
    throw new ApiError("Unable to delete chunking profile", result.response.status, result.error);
  }
}

export function useChunkingProfilesQuery() {
  return useQuery({ queryKey: chunkingProfileKeys.all, queryFn: listChunkingProfiles });
}

export function useChunkerDefinitionsQuery() {
  return useQuery({ queryKey: chunkingProfileKeys.definitions, queryFn: listChunkerDefinitions });
}

function useInvalidateChunkingProfiles() {
  const queryClient = useQueryClient();
  return async () => queryClient.invalidateQueries({ queryKey: chunkingProfileKeys.all });
}

export function useCreateChunkingProfileMutation() {
  const invalidate = useInvalidateChunkingProfiles();
  return useMutation({
    mutationFn: createChunkingProfile,
    onSuccess: async () => invalidate()
  });
}

export function useUpdateChunkingProfileMutation(profileId: number) {
  const invalidate = useInvalidateChunkingProfiles();
  return useMutation({
    mutationFn: (input: ChunkingProfileUpdate) => updateChunkingProfile(profileId, input),
    onSuccess: async () => invalidate()
  });
}

export function useCopyChunkingProfileMutation(profileId: number) {
  const invalidate = useInvalidateChunkingProfiles();
  return useMutation({
    mutationFn: (input: ChunkingProfileCopy) => copyChunkingProfile(profileId, input),
    onSuccess: async () => invalidate()
  });
}

export function useDeleteChunkingProfileMutation(profileId: number) {
  const invalidate = useInvalidateChunkingProfiles();
  return useMutation({
    mutationFn: () => deleteChunkingProfile(profileId),
    onSuccess: async () => invalidate()
  });
}
