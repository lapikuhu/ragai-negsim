import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, subscribeToUnauthorized } from "@/api/client";
import { useCurrentUserQuery, useLoginMutation } from "@/features/auth/authQueries";
import { clearAccessToken, getAccessToken } from "@/features/auth/authStorage";
import type { LoginInput } from "@/features/auth/authQueries";

const EXPIRED_SESSION_MESSAGE = "Your session expired or is no longer valid. Sign in again.";
const UNVERIFIED_SESSION_MESSAGE = "We couldn’t verify your session. Sign in again.";

export type AuthStatus = "unauthenticated" | "validating" | "authenticated" | "validation-failed";

type AuthContextValue = {
  token: string | null;
  user: ReturnType<typeof useCurrentUserQuery>["data"] | null;
  status: AuthStatus;
  isAuthenticated: boolean;
  isLoading: boolean;
  sessionError: string | null;
  login: (input: LoginInput) => Promise<void>;
  logout: () => void;
  clearSessionError: () => void;
  hasRole: (...roles: string[]) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);
/*
 * Provides authentication context to the application.
 * Manages user session, login, logout, and session validation.
 * @param children The child components that will have access to the authentication context.
 * @returns The authentication context provider component.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setTokenState] = useState<string | null>(() => getAccessToken());
  const [sessionError, setSessionError] = useState<string | null>(null);
  const loginMutation = useLoginMutation();
  const meQuery = useCurrentUserQuery(Boolean(token));

  const endSession = useCallback((message: string | null) => {
    clearAccessToken();
    setTokenState(null);
    setSessionError(message);
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => subscribeToUnauthorized(() => endSession(EXPIRED_SESSION_MESSAGE)), [endSession]);

  useEffect(() => {
    if (!token || !meQuery.isError) {
      return;
    }
    const message = meQuery.error instanceof ApiError && meQuery.error.status === 401
      ? EXPIRED_SESSION_MESSAGE
      : UNVERIFIED_SESSION_MESSAGE;
    endSession(message);
  }, [endSession, meQuery.error, meQuery.isError, token]);

  const value = useMemo<AuthContextValue>(() => {
    const user = token && meQuery.isSuccess ? meQuery.data : null;
    const roleNames = new Set(user?.roles?.map((role) => role.name) ?? []);
    const status: AuthStatus = token
      ? user
        ? "authenticated"
        : meQuery.isError
          ? "validation-failed"
          : "validating"
      : sessionError
        ? "validation-failed"
        : "unauthenticated";

    return {
      token,
      user,
      status,
      isAuthenticated: status === "authenticated",
      isLoading: loginMutation.isPending || status === "validating",
      sessionError,
      async login(input) {
        setSessionError(null);
        const tokenResult = await loginMutation.mutateAsync(input);
        setTokenState(tokenResult.access_token);
      },
      logout() {
        endSession(null);
      },
      clearSessionError() {
        setSessionError(null);
      },
      hasRole(...roles) {
        return roles.some((role) => roleNames.has(role));
      }
    };
  }, [endSession, loginMutation, meQuery.data, meQuery.isPending, meQuery.isSuccess, sessionError, token]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return value;
}
