import { useQuery } from "@tanstack/react-query";
import { apiClient, ApiError, unwrapResult } from "@/api/client";
import { coerceRawDocumentRead, type RawDocumentRead, type SessionRead, type SimulationRead } from "@/api/types";

type DashboardData = {
  simulations: SimulationRead[];
  documents: RawDocumentRead[];
  sessions: SessionRead[];
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

export async function fetchDashboardData() {
  const [simulations, documents, sessions] = await Promise.all([
    safeList(async () => {
      const result = await apiClient.GET("/simulations/", { params: { query: { skip: 0, limit: 5 } } });
      return unwrapResult<SimulationRead[]>(result, "Unable to load simulations");
    }, []),
    safeList(async () => {
      const result = await apiClient.GET("/raw-documents/", { params: { query: { skip: 0, limit: 5 } } });
      return unwrapResult(result, "Unable to load documents").map(coerceRawDocumentRead);
    }, []),
    safeList(async () => {
      const result = await apiClient.GET("/sessions/", { params: { query: { skip: 0, limit: 5 } } });
      return unwrapResult<SessionRead[]>(result, "Unable to load sessions");
    }, [])
  ]);

  return { simulations, documents, sessions } satisfies DashboardData;
}

export function useDashboardQuery() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: fetchDashboardData
  });
}
