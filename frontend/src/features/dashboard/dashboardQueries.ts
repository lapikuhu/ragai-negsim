import { useQuery } from "@tanstack/react-query";
import { apiClient, ApiError, unwrapResult } from "@/api/client";
import {
  coerceRawDocumentRead,
  type CorpusRead,
  type RagProfileRead,
  type RawDocumentRead,
  type ScenarioPublicRead,
  type SimulationRead,
  type UserRead
} from "@/api/types";

export type DashboardData = {
  simulations: SimulationRead[];
  documents: RawDocumentRead[];
  corpora: CorpusRead[];
  users: UserRead[];
  scenarios: ScenarioPublicRead[];
  ragProfiles: RagProfileRead[];
};

async function safeList<T>(factory: () => Promise<T>, fallback: T) {
  try {
    return await factory();
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return fallback;
    }
    throw error;
  }
}

function byNewestTimestamp<T>(getTimestamp: (item: T) => string | null | undefined) {
  return (left: T, right: T) =>
    new Date(getTimestamp(right) ?? 0).getTime() - new Date(getTimestamp(left) ?? 0).getTime();
}

export async function fetchDashboardData(): Promise<DashboardData> {
  const [simulations, documents, corpora, users, scenarios, ragProfiles] = await Promise.all([
    safeList(async () => {
      const result = await apiClient.GET("/simulations/", { params: { query: { skip: 0, limit: 5 } } });
      return unwrapResult<SimulationRead[]>(result, "Unable to load simulations");
    }, []),
    safeList(async () => {
      const result = await apiClient.GET("/raw-documents/", { params: { query: { skip: 0, limit: 5 } } });
      return unwrapResult(result, "Unable to load documents").map(coerceRawDocumentRead);
    }, []),
    safeList(async () => {
      const result = await apiClient.GET("/corpora/", { params: { query: { skip: 0, limit: 50 } } });
      const items = unwrapResult<CorpusRead[]>(result, "Unable to load corpora");
      return [...items].sort(byNewestTimestamp((corpus) => corpus.created_at)).slice(0, 5);
    }, []),
    safeList(async () => {
      const result = await apiClient.GET("/users/", { params: { query: { skip: 0, limit: 5 } } });
      return unwrapResult<UserRead[]>(result, "Unable to load users");
    }, []),
    safeList(async () => {
      const result = await apiClient.GET("/scenarios/", { params: { query: { skip: 0, limit: 50 } } });
      const items = unwrapResult<ScenarioPublicRead[]>(result, "Unable to load scenarios");
      return [...items].sort(byNewestTimestamp((scenario) => scenario.last_updated)).slice(0, 5);
    }, []),
    safeList(async () => {
      const result = await apiClient.GET("/rag-profiles/", { params: { query: { skip: 0, limit: 50 } } });
      const items = unwrapResult<RagProfileRead[]>(result, "Unable to load RAG profiles");
      return [...items].sort(byNewestTimestamp((profile) => profile.last_updated)).slice(0, 5);
    }, [])
  ]);

  return { simulations, documents, corpora, users, scenarios, ragProfiles } satisfies DashboardData;
}

export function useDashboardQuery() {
  return useQuery<DashboardData, Error>({
    queryKey: ["dashboard"],
    queryFn: fetchDashboardData
  });
}
