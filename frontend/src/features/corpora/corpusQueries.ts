import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, ApiError, apiFetch, unwrapResult } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import type { ApiComponents, CorpusRead } from "@/api/types";

type CorpusCreate = ApiComponents["schemas"]["CorpusCreate"];
type CorpusIngestResult = ApiComponents["schemas"]["CorpusIngestResult"];
type CorpusChunkResult = ApiComponents["schemas"]["CorpusChunkResult"];
type CorpusEmbeddingBuildQueued = ApiComponents["schemas"]["CorpusEmbeddingBuildQueued"];
type CorpusEmbeddingBuildRequest = ApiComponents["schemas"]["CorpusEmbeddingBuildRequest"];

export const corpusKeys = {
  all: ["corpora"] as const
};

export async function listCorpora() {
  const result = await apiClient.GET("/corpora/", { params: { query: { skip: 0, limit: 50 } } });
  return unwrapResult<CorpusRead[]>(result, "Unable to load corpora");
}

async function createCorpus(input: CorpusCreate) {
  const response = await apiFetch(`${getApiBaseUrl()}/corpora/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(input)
  });
  const payload = await response.text();

  if (!response.ok) {
    let detail: unknown = payload;
    try {
      detail = JSON.parse(payload);
    } catch {
      // Keep plain-text payload when the backend does not return JSON.
    }
    throw new ApiError("Unable to create corpus", response.status, detail);
  }

  return JSON.parse(payload) as CorpusRead;
}

async function ingestCorpus(corpusId: number, profileId: number) {
  const result = await apiClient.POST("/corpora/{corpus_id}/chunking-profiles/{profile_id}/ingest", {
    params: { path: { corpus_id: corpusId, profile_id: profileId } }
  });
  return unwrapResult<CorpusIngestResult>(result, "Unable to ingest corpus");
}

async function chunkCorpus(corpusId: number, profileId: number) {
  const result = await apiClient.POST("/corpora/{corpus_id}/chunking-profiles/{profile_id}/chunk", {
    params: { path: { corpus_id: corpusId, profile_id: profileId } }
  });
  return unwrapResult<CorpusChunkResult>(result, "Unable to chunk corpus");
}

async function queueEmbedJob(
  corpusId: number,
  profileId: number,
  vectorStoreId: number,
  input: CorpusEmbeddingBuildRequest
) {
  const result = await apiClient.POST(
    "/corpora/{corpus_id}/chunking-profiles/{profile_id}/vector-stores/{vector_store_id}/embed-jobs",
    {
      params: { path: { corpus_id: corpusId, profile_id: profileId, vector_store_id: vectorStoreId } },
      body: input
    }
  );
  return unwrapResult<CorpusEmbeddingBuildQueued>(result, "Unable to queue embedding job");
}

export function useCorporaQuery() {
  return useQuery({ queryKey: corpusKeys.all, queryFn: listCorpora });
}

function useInvalidateCorpora() {
  const queryClient = useQueryClient();
  return async () => {
    await queryClient.invalidateQueries({ queryKey: corpusKeys.all });
  };
}

export function useCreateCorpusMutation() {
  const invalidate = useInvalidateCorpora();
  return useMutation({
    mutationFn: createCorpus,
    onSuccess: async () => invalidate()
  });
}

export function useIngestCorpusMutation(corpusId: number) {
  const invalidate = useInvalidateCorpora();
  return useMutation({
    mutationFn: (profileId: number) => ingestCorpus(corpusId, profileId),
    onSuccess: async () => invalidate()
  });
}

export function useChunkCorpusMutation(corpusId: number) {
  const invalidate = useInvalidateCorpora();
  return useMutation({
    mutationFn: (profileId: number) => chunkCorpus(corpusId, profileId),
    onSuccess: async () => invalidate()
  });
}

export function useQueueEmbedJobMutation(corpusId: number, profileId: number, vectorStoreId: number) {
  const invalidate = useInvalidateCorpora();
  return useMutation({
    mutationFn: (input: CorpusEmbeddingBuildRequest) =>
      queueEmbedJob(corpusId, profileId, vectorStoreId, input),
    onSuccess: async () => invalidate()
  });
}
