import { useQuery } from "@tanstack/react-query";
import { apiClient, unwrapResult } from "@/api/client";
import type { ChunkingProfileRead, CorpusIndexRead, EmbeddingModelRead, VectorStoreRead } from "@/api/types";
export { listVectorStores, useVectorStoresQuery, vectorStoreKeys } from "@/features/vectorStores/vectorStoreQueries";

export const corpusIndexKeys = {
  all: ["corpus-indices"] as const,
  detail: (indexId: number) => ["corpus-indices", indexId] as const,
  chunkingProfiles: ["chunking-profiles"] as const,
  embeddingModels: ["embedding-models"] as const
};

export async function listCorpusIndices() {
  const result = await apiClient.GET("/corpus-indices/", { params: { query: { skip: 0, limit: 50 } } });
  return unwrapResult<CorpusIndexRead[]>(result, "Unable to load corpus indices");
}

export async function getCorpusIndex(indexId: number) {
  const result = await apiClient.GET("/corpus-indices/{index_id}", {
    params: { path: { index_id: indexId } }
  });
  return unwrapResult<CorpusIndexRead>(result, "Unable to load corpus index");
}

export async function listChunkingProfiles() {
  const result = await apiClient.GET("/chunking-profiles/", { params: { query: { skip: 0, limit: 50 } } });
  return unwrapResult<ChunkingProfileRead[]>(result, "Unable to load chunking profiles");
}

export async function listEmbeddingModels() {
  const result = await apiClient.GET("/embeddings/models");
  return unwrapResult<EmbeddingModelRead[]>(result, "Unable to load embedding models");
}

export function useCorpusIndicesQuery() {
  return useQuery({ queryKey: corpusIndexKeys.all, queryFn: listCorpusIndices });
}

export function useCorpusIndexDetailQuery(indexId: number) {
  return useQuery({
    queryKey: corpusIndexKeys.detail(indexId),
    queryFn: () => getCorpusIndex(indexId),
    enabled: Number.isFinite(indexId)
  });
}

export function useChunkingProfilesQuery() {
  return useQuery({ queryKey: corpusIndexKeys.chunkingProfiles, queryFn: listChunkingProfiles });
}

export function useEmbeddingModelsQuery() {
  return useQuery({ queryKey: corpusIndexKeys.embeddingModels, queryFn: listEmbeddingModels });
}
