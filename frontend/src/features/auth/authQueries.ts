import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, unwrapResult } from "@/api/client";
import { clearAccessToken, setAccessToken } from "@/features/auth/authStorage";
import type { Token, UserRead } from "@/api/types";

export const authKeys = {
  me: ["auth", "me"] as const
};

export type LoginInput = {
  username: string;
  password: string;
};

export async function loginRequest(input: LoginInput) {
  const result = await apiClient.POST("/users/login", {
    body: {
      scope: "",
      username: input.username,
      password: input.password
    },
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    },
    bodySerializer(body) {
      return new URLSearchParams(
        Object.entries(body as Record<string, string>).map(([key, value]) => [key, value ?? ""])
      );
    }
  });

  const token = unwrapResult<Token>(result, "Login failed");
  setAccessToken(token.access_token);
  return token;
}

export async function fetchCurrentUser() {
  const result = await apiClient.GET("/users/me");
  return unwrapResult<UserRead>(result, "Unable to load current user");
}

export function useCurrentUserQuery(enabled: boolean) {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: fetchCurrentUser,
    enabled
  });
}

export function useLoginMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: loginRequest,
    async onSuccess() {
      await queryClient.invalidateQueries({ queryKey: authKeys.me });
    }
  });
}

export function useLogout() {
  const queryClient = useQueryClient();

  return () => {
    clearAccessToken();
    queryClient.removeQueries({ queryKey: authKeys.me });
  };
}
