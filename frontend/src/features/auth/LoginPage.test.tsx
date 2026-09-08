import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { setAccessToken } from "@/api/clientConfig";
import { AuthProvider, useAuth } from "@/app/AuthProvider";
import { LoginPage } from "@/features/auth/LoginPage";

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

function DestinationProbe() {
  const location = useLocation();
  const auth = useAuth();
  return (
    <div>
      <h1>Protected destination</h1>
      <span data-testid="destination">{location.pathname}{location.search}{location.hash}</span>
      <span data-testid="destination-user">{auth.user?.username ?? "no-user"}</span>
    </div>
  );
}

function renderLogin(state?: { from: { pathname: string; search?: string; hash?: string } }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[{ pathname: "/login", state }]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/documents" element={<DestinationProbe />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    setAccessToken(null);
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("keeps the destination locked until login credentials resolve to a current user", async () => {
    const user = userEvent.setup();
    let resolveCurrentUser!: (response: Response) => void;
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ access_token: "fresh-token", token_type: "bearer" }))
      .mockReturnValueOnce(new Promise<Response>((resolve) => {
        resolveCurrentUser = resolve;
      }));
    renderLogin({ from: { pathname: "/documents", search: "?tab=recent", hash: "#top" } });

    await user.type(screen.getByLabelText("Username"), "alice");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(screen.getByText("Checking your session...")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Protected destination" })).not.toBeInTheDocument();

    resolveCurrentUser(jsonResponse(currentUser));

    expect(await screen.findByRole("heading", { name: "Protected destination" })).toBeInTheDocument();
    expect(screen.getByTestId("destination")).toHaveTextContent("/documents?tab=recent#top");
    expect(screen.getByTestId("destination-user")).toHaveTextContent("alice");
  });

  it("shows a session-validation error separately from credential errors", async () => {
    setAccessToken("expired-token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ detail: "Invalid token" }, 401));

    renderLogin();

    expect(await screen.findByText("Your session expired or is no longer valid. Sign in again.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByText("Operational Console")).not.toBeInTheDocument();
  });

  it("shows a credential error without treating it as a session invalidation", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ detail: "Incorrect username or password" }, 401));
    renderLogin();

    await user.type(screen.getByLabelText("Username"), "alice");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Incorrect username or password")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });
});
