import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiClient, apiFetch, unwrapResult } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import type { ApiComponents, UserRead } from "@/api/types";

type RoleRead = ApiComponents["schemas"]["RoleRead"];
type UserCreate = ApiComponents["schemas"]["UserCreate"];
type UserCreatedResponse = ApiComponents["schemas"]["UserCreatedResponse"];
type UserUpdate = ApiComponents["schemas"]["UserUpdate"];

export const userKeys = {
  all: ["users"] as const,
  roles: ["users", "roles"] as const
};

export async function listUsers() {
  const result = await apiClient.GET("/users/", { params: { query: { skip: 0, limit: 50 } } });
  return unwrapResult<UserRead[]>(result, "Unable to load users");
}

export async function listUserRoles() {
  const result = await apiClient.GET("/users/roles");
  return unwrapResult<RoleRead[]>(result, "Unable to load roles");
}

async function jsonRequest<T>(path: string, init: RequestInit, fallback: string) {
  const response = await apiFetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {})
    }
  });
  const detail = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(fallback, response.status, detail);
  }
  return detail as T;
}

async function createUser(input: UserCreate) {
  return jsonRequest<UserCreatedResponse>(
    "/users/register",
    {
      method: "POST",
      body: JSON.stringify(input)
    },
    "Unable to create user"
  );
}

async function updateUser(userId: number, input: UserUpdate) {
  return jsonRequest<UserRead>(
    `/users/${userId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input)
    },
    "Unable to update user"
  );
}

export function useUsersQuery() {
  return useQuery({ queryKey: userKeys.all, queryFn: listUsers });
}

export function useUserRolesQuery() {
  return useQuery({ queryKey: userKeys.roles, queryFn: listUserRoles });
}

function useInvalidateUsers() {
  const queryClient = useQueryClient();
  return async () => queryClient.invalidateQueries({ queryKey: userKeys.all });
}

export function useCreateUserMutation() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: createUser,
    onSuccess: async () => invalidate()
  });
}

export function useUpdateUserMutation(userId: number) {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: (input: UserUpdate) => updateUser(userId, input),
    onSuccess: async () => invalidate()
  });
}
