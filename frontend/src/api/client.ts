import createClient from "openapi-fetch";
import { clearAccessToken, getAccessToken, getApiBaseUrl } from "@/api/clientConfig";
import type { ApiPaths } from "@/api/types";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function authFetch(input: RequestInfo | URL, init?: RequestInit) {
  const headers = new Headers(init?.headers);
  const token = getAccessToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(input, {
    ...init,
    headers
  });

  if (response.status === 401) {
    clearAccessToken();
  }

  return response;
}

export const apiClient = createClient<ApiPaths>({
  baseUrl: getApiBaseUrl(),
  fetch: authFetch
});

export function getErrorMessage(error: unknown, fallback = "Request failed") {
  if (error instanceof ApiError) {
    if (typeof error.detail === "string") {
      return error.detail;
    }
    if (
      error.detail &&
      typeof error.detail === "object" &&
      "detail" in error.detail &&
      typeof (error.detail as { detail?: unknown }).detail === "string"
    ) {
      return (error.detail as { detail: string }).detail;
    }
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}

type ApiResult<T> = { data?: T; error?: unknown; response: Response };

export function unwrapResult<T>(result: ApiResult<T>, fallback: string) {
  if (result.error) {
    throw new ApiError(fallback, result.response.status, result.error);
  }
  if (typeof result.data === "undefined") {
    throw new ApiError(fallback, result.response.status, result.error);
  }
  return result.data;
}
