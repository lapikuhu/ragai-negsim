import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiClient, unwrapResult } from "@/api/client";
import type { ApiComponents, ChunkingProfileRead } from "@/api/types";

type ChunkingProfileCreate = ApiComponents["schemas"]["ChunkingProfileCreate"];
type ChunkingProfileUpdate = ApiComponents["schemas"]["ChunkingProfileUpdate"];
type ChunkingProfileCopy = ApiComponents["schemas"]["ChunkingProfileCopy"];

export const chunkingProfileKeys = {
  all: ["chunking-profiles"] as const
};

export async function listChunkingProfiles() {
  const result = await apiClient.GET("/chunking-profiles/", { params: { query: { skip: 0, limit: 50 } } });
  return unwrapResult<ChunkingProfileRead[]>(result, "Unable to load chunking profiles");
}

async function createChunkingProfile(input: ChunkingProfileCreate) {
  const result = await apiClient.POST("/chunking-profiles/", { body: input });
  return unwrapResult<ChunkingProfileRead>(result, "Unable to create chunking profile");
}

async function updateChunkingProfile(profileId: number, input: ChunkingProfileUpdate) {
  const result = await apiClient.PATCH("/chunking-profiles/{profile_id}", {
    params: { path: { profile_id: profileId } },
    body: input
  });
  return unwrapResult<ChunkingProfileRead>(result, "Unable to update chunking profile");
}

async function copyChunkingProfile(profileId: number, input: ChunkingProfileCopy) {
  const result = await apiClient.POST("/chunking-profiles/{profile_id}/copy", {
    params: { path: { profile_id: profileId } },
    body: input
  });
  return unwrapResult<ChunkingProfileRead>(result, "Unable to copy chunking profile");
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
