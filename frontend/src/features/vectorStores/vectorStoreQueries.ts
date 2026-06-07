import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiClient, apiFetch, unwrapResult } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import type { ApiComponents, VectorStoreRead } from "@/api/types";

type VectorStoreCreate = ApiComponents["schemas"]["VectorStoreCreate"];
type VectorStoreUpdate = ApiComponents["schemas"]["VectorStoreUpdate"];

export const vectorStoreKeys = {
  all: ["vector-stores"] as const
};

export async function listVectorStores() {
  const result = await apiClient.GET("/vector-stores/", { params: { query: { skip: 0, limit: 50 } } });
  return unwrapResult<VectorStoreRead[]>(result, "Unable to load vector stores");
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

async function createVectorStore(input: VectorStoreCreate) {
  return jsonRequest<VectorStoreRead>(
    "/vector-stores/",
    {
      method: "POST",
      body: JSON.stringify(input)
    },
    "Unable to create vector store"
  );
}

async function updateVectorStore(vectorStoreId: number, input: VectorStoreUpdate) {
  return jsonRequest<VectorStoreRead>(
    `/vector-stores/${vectorStoreId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input)
    },
    "Unable to update vector store"
  );
}

async function deleteVectorStore(vectorStoreId: number) {
  const result = await apiClient.DELETE("/vector-stores/{vector_store_id}", {
    params: { path: { vector_store_id: vectorStoreId } }
  });

  if (result.error) {
    throw new ApiError("Unable to delete vector store", result.response.status, result.error);
  }
}

export function useVectorStoresQuery() {
  return useQuery({ queryKey: vectorStoreKeys.all, queryFn: listVectorStores });
}

function useInvalidateVectorStores() {
  const queryClient = useQueryClient();
  return async () => queryClient.invalidateQueries({ queryKey: vectorStoreKeys.all });
}

export function useCreateVectorStoreMutation() {
  const invalidate = useInvalidateVectorStores();
  return useMutation({
    mutationFn: createVectorStore,
    onSuccess: async () => invalidate()
  });
}

export function useUpdateVectorStoreMutation(vectorStoreId: number) {
  const invalidate = useInvalidateVectorStores();
  return useMutation({
    mutationFn: (input: VectorStoreUpdate) => updateVectorStore(vectorStoreId, input),
    onSuccess: async () => invalidate()
  });
}

export function useDeleteVectorStoreMutation(vectorStoreId: number) {
  const invalidate = useInvalidateVectorStores();
  return useMutation({
    mutationFn: () => deleteVectorStore(vectorStoreId),
    onSuccess: async () => invalidate()
  });
}