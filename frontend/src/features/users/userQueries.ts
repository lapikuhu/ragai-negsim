import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiClient, apiFetch, unwrapResult } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";
import type { ApiComponents, SimulationRead, UserRead } from "@/api/types";

type RoleRead = ApiComponents["schemas"]["RoleRead"];
type UserCreate = ApiComponents["schemas"]["UserCreate"];
type UserCreatedResponse = ApiComponents["schemas"]["UserCreatedResponse"];
type UserUpdate = ApiComponents["schemas"]["UserUpdate"];

export const userKeys = {
  all: ["users"] as const,
  detail: (username: string) => ["users", username] as const,
  simulations: (userId: number) => ["users", userId, "simulations"] as const,
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

export async function getUserByUsername(username: string) {
  const result = await apiClient.GET("/users/{username}", {
    params: { path: { username } }
  });
  return unwrapResult<UserRead>(result, "Unable to load student");
}

export async function listStudentSimulations(userId: number) {
  const result = await apiClient.GET("/simulations/", {
    params: { query: { skip: 0, limit: 50, participant_id: userId } }
  });
  return unwrapResult<SimulationRead[]>(result, "Unable to load student simulations");
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

export function useUserDetailQuery(username: string) {
  return useQuery({
    queryKey: userKeys.detail(username),
    queryFn: () => getUserByUsername(username),
    enabled: Boolean(username)
  });
}

export function useStudentSimulationsQuery(userId?: number) {
  return useQuery({
    queryKey: userKeys.simulations(userId ?? 0),
    queryFn: () => listStudentSimulations(userId!),
    enabled: userId !== undefined
  });
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
