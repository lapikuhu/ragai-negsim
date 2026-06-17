import { useQuery } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import type { LLMModelCatalogResponse } from "@/api/types";

export const llmModelKeys = {
  catalog: ["llm-models", "catalog"] as const,
};

async function getLlmModelCatalog() {
  const response = await apiFetch(`${getApiBaseUrl()}/llm-models/catalog`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  const detail = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError("Unable to load LLM model catalog", response.status, detail);
  }
  if (!isLlmModelCatalogResponse(detail)) {
    throw new ApiError("Unable to load LLM model catalog", response.status, detail);
  }
  return detail as LLMModelCatalogResponse;
}

function isLlmModelCatalogResponse(value: unknown): value is LLMModelCatalogResponse {
  return Boolean(value) && typeof value === "object" && Array.isArray((value as LLMModelCatalogResponse).providers);
}

export function useLlmModelCatalogQuery() {
  return useQuery({ queryKey: llmModelKeys.catalog, queryFn: getLlmModelCatalog });
}