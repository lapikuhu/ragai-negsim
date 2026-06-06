import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiClient, unwrapResult } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
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
  const body = new URLSearchParams({
    // Send the exact OAuth2 password form Swagger uses to avoid request-shape mismatches.
    client_id: "",
    client_secret: "",
    scope: "",
    username: input.username,
    password: input.password
  });

  const response = await fetch(`${getApiBaseUrl()}/users/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Accept: "application/json"
    },
    body: body.toString()
  });

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError("Login failed", response.status, payload);
  }

  const token = payload as Token;
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
