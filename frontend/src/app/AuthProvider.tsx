import { createContext, useContext, useMemo, useState } from "react";
import { useCurrentUserQuery, useLoginMutation, useLogout } from "@/features/auth/authQueries";
import { getAccessToken } from "@/features/auth/authStorage";
import type { LoginInput } from "@/features/auth/authQueries";

type AuthContextValue = {
  token: string | null;
  user: ReturnType<typeof useCurrentUserQuery>["data"] | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (input: LoginInput) => Promise<void>;
  logout: () => void;
  hasRole: (...roles: string[]) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getAccessToken());
  const loginMutation = useLoginMutation();
  const logout = useLogout();
  const meQuery = useCurrentUserQuery(Boolean(token));

  const value = useMemo<AuthContextValue>(() => {
    const roleNames = new Set(meQuery.data?.roles?.map((role) => role.name) ?? []);

    return {
      token,
      user: meQuery.data ?? null,
      isAuthenticated: Boolean(token),
      isLoading: loginMutation.isPending || (Boolean(token) && meQuery.isLoading),
      async login(input) {
        const tokenResult = await loginMutation.mutateAsync(input);
        setTokenState(tokenResult.access_token);
      },
      logout() {
        logout();
        setTokenState(null);
      },
      hasRole(...roles) {
        return roles.some((role) => roleNames.has(role));
      }
    };
  }, [loginMutation, logout, meQuery.data, meQuery.isLoading, token]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return value;
}
