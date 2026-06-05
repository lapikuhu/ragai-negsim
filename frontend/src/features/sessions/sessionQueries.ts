import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, unwrapResult } from "@/api/client";
import type { ApiComponents, SessionRead } from "@/api/types";

type SessionCreateRequest = ApiComponents["schemas"]["SessionCreateRequest"];
type SessionUpdateRequest = ApiComponents["schemas"]["SessionUpdateRequest"];
type SessionHeartbeat = ApiComponents["schemas"]["SessionHeartbeat"];
type SessionEnd = ApiComponents["schemas"]["SessionEnd"];

export const sessionKeys = {
  all: ["sessions"] as const,
  detail: (sessionId: number) => ["sessions", sessionId] as const
};

export async function listSessions() {
  const result = await apiClient.GET("/sessions/", { params: { query: { skip: 0, limit: 50 } } });
  return unwrapResult<SessionRead[]>(result, "Unable to load sessions");
}

export async function getSession(sessionId: number) {
  const result = await apiClient.GET("/sessions/{session_id}", {
    params: { path: { session_id: sessionId } }
  });
  return unwrapResult<SessionRead>(result, "Unable to load session");
}

async function createSession(input: SessionCreateRequest) {
  const result = await apiClient.POST("/sessions/", { body: input });
  return unwrapResult<SessionRead>(result, "Unable to create session");
}

async function updateSession(sessionId: number, input: SessionUpdateRequest) {
  const result = await apiClient.PATCH("/sessions/{session_id}", {
    params: { path: { session_id: sessionId } },
    body: input
  });
  return unwrapResult<SessionRead>(result, "Unable to update session");
}

async function heartbeatSession(sessionId: number, input: SessionHeartbeat) {
  const result = await apiClient.POST("/sessions/{session_id}/heartbeat", {
    params: { path: { session_id: sessionId } },
    body: input
  });
  return unwrapResult<SessionRead>(result, "Unable to heartbeat session");
}

async function endSession(sessionId: number, input: SessionEnd) {
  const result = await apiClient.POST("/sessions/{session_id}/end", {
    params: { path: { session_id: sessionId } },
    body: input
  });
  return unwrapResult<SessionRead>(result, "Unable to end session");
}

export function useSessionsQuery() {
  return useQuery({ queryKey: sessionKeys.all, queryFn: listSessions });
}

export function useSessionDetailQuery(sessionId: number) {
  return useQuery({
    queryKey: sessionKeys.detail(sessionId),
    queryFn: () => getSession(sessionId),
    enabled: Number.isFinite(sessionId)
  });
}

function useInvalidateSessions() {
  const queryClient = useQueryClient();
  return async (sessionId?: number) => {
    await queryClient.invalidateQueries({ queryKey: sessionKeys.all });
    if (typeof sessionId === "number") {
      await queryClient.invalidateQueries({ queryKey: sessionKeys.detail(sessionId) });
    }
  };
}

export function useCreateSessionMutation() {
  const invalidate = useInvalidateSessions();
  return useMutation({
    mutationFn: createSession,
    onSuccess: async (session) => invalidate(session.id)
  });
}

export function useUpdateSessionMutation(sessionId: number) {
  const invalidate = useInvalidateSessions();
  return useMutation({
    mutationFn: (input: SessionUpdateRequest) => updateSession(sessionId, input),
    onSuccess: async () => invalidate(sessionId)
  });
}

export function useHeartbeatSessionMutation(sessionId: number) {
  const invalidate = useInvalidateSessions();
  return useMutation({
    mutationFn: (input: SessionHeartbeat) => heartbeatSession(sessionId, input),
    onSuccess: async () => invalidate(sessionId)
  });
}

export function useEndSessionMutation(sessionId: number) {
  const invalidate = useInvalidateSessions();
  return useMutation({
    mutationFn: (input: SessionEnd) => endSession(sessionId, input),
    onSuccess: async () => invalidate(sessionId)
  });
}
