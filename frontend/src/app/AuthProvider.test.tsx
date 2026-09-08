import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "@/api/client";
import { setAccessToken } from "@/api/clientConfig";
import { AuthProvider, useAuth } from "@/app/AuthProvider";

const currentUser = {
  id: 7,
  username: "alice",
  user_email_address: "alice@example.com",
  roles: [{ id: 2, name: "student" }]
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

function AuthProbe() {
  const auth = useAuth();

  return (
    <div>
      <span data-testid="status">{auth.status}</span>
      <span data-testid="username">{auth.user?.username ?? "no-user"}</span>
      <span data-testid="session-error">{auth.sessionError ?? "no-error"}</span>
      <button type="button" onClick={auth.logout}>Log out</button>
      <button type="button" onClick={auth.clearSessionError}>Clear session error</button>
    </div>
  );
}

function renderAuth() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    </QueryClientProvider>
  );
  return queryClient;
}

describe("AuthProvider", () => {
  beforeEach(() => {
    setAccessToken(null);
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("is unauthenticated without requesting the current user when no token exists", () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");

    renderAuth();

    expect(screen.getByTestId("status").textContent).toBe("unauthenticated");
    expect(screen.getByTestId("username")).toHaveTextContent("no-user");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("stays validating until a stored token loads a current user", async () => {
    setAccessToken("valid-token");
    let resolveCurrentUser!: (response: Response) => void;
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveCurrentUser = resolve;
      })
    );

    renderAuth();

    expect(screen.getByTestId("status").textContent).toBe("validating");
    expect(screen.getByTestId("username")).toHaveTextContent("no-user");

    resolveCurrentUser(jsonResponse(currentUser));

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));
    expect(screen.getByTestId("username")).toHaveTextContent("alice");
  });

  it("rejects an invalid stored token and reports an expired session", async () => {
    setAccessToken("expired-token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ detail: "Invalid token" }, 401));

    renderAuth();

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("validation-failed"));
    expect(screen.getByTestId("username")).toHaveTextContent("no-user");
    expect(screen.getByTestId("session-error")).toHaveTextContent(
      "Your session expired or is no longer valid. Sign in again."
    );
    expect(localStorage.getItem("ragai-negsim.access-token")).toBeNull();
  });

  it("retries a server validation failure once before rejecting the session", async () => {
    setAccessToken("unverifiable-token");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ detail: "Unavailable" }, 503));

    renderAuth();

    await waitFor(() => expect(screen.getByTestId("session-error")).toHaveTextContent(
      "We couldn’t verify your session. Sign in again."
    ));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("status").textContent).toBe("validation-failed");
    expect(localStorage.getItem("ragai-negsim.access-token")).toBeNull();
  });

  it("clears all cached data on manual logout without reporting an error", async () => {
    setAccessToken("valid-token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(currentUser));
    const queryClient = renderAuth();
    queryClient.setQueryData(["protected-resource"], { secret: true });
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));

    fireEvent.click(screen.getByRole("button", { name: "Log out" }));

    expect(screen.getByTestId("status").textContent).toBe("unauthenticated");
    expect(screen.getByTestId("session-error")).toHaveTextContent("no-error");
    expect(queryClient.getQueryData(["protected-resource"])).toBeUndefined();
  });

  it("invalidates an authenticated session when a later API request returns 401", async () => {
    setAccessToken("valid-token");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(jsonResponse(currentUser));
    const queryClient = renderAuth();
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));
    queryClient.setQueryData(["protected-resource"], { secret: true });
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "Expired" }, 401));

    await apiFetch("http://localhost/simulations/");

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("validation-failed"));
    expect(screen.getByTestId("session-error")).toHaveTextContent(
      "Your session expired or is no longer valid. Sign in again."
    );
    expect(queryClient.getQueryData(["protected-resource"])).toBeUndefined();
  });
});
