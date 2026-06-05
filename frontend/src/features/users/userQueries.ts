import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, unwrapResult } from "@/api/client";
import type { ApiComponents, UserRead } from "@/api/types";

type UserCreate = ApiComponents["schemas"]["UserCreate"];
type UserCreatedResponse = ApiComponents["schemas"]["UserCreatedResponse"];
type UserUpdate = ApiComponents["schemas"]["UserUpdate"];

export const userKeys = {
  all: ["users"] as const
};

export async function listUsers() {
  const result = await apiClient.GET("/users/", { params: { query: { skip: 0, limit: 50 } } });
  return unwrapResult<UserRead[]>(result, "Unable to load users");
}

async function createUser(input: UserCreate) {
  const result = await apiClient.POST("/users/register", { body: input });
  return unwrapResult<UserCreatedResponse>(result, "Unable to create user");
}

async function updateUser(userId: number, input: UserUpdate) {
  const result = await apiClient.PATCH("/users/{user_id}", {
    params: { path: { user_id: userId } },
    body: input
  });
  return unwrapResult<UserRead>(result, "Unable to update user");
}

export function useUsersQuery() {
  return useQuery({ queryKey: userKeys.all, queryFn: listUsers });
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
