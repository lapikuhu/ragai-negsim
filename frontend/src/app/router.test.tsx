import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const authState = vi.hoisted(() => ({
  isAuthenticated: true,
  isLoading: false,
  status: "authenticated" as "unauthenticated" | "validating" | "authenticated" | "validation-failed",
  roles: ["teacher"] as string[],
  sessionError: null as string | null,
  login: vi.fn(),
  logout: vi.fn(),
  clearSessionError: vi.fn()
}));

vi.mock("@/app/AuthProvider", () => ({
  useAuth: () => ({
    ...authState,
    hasRole: (...roles: string[]) => roles.some((role) => authState.roles.includes(role)),
    user: {
      username: "router-test-user",
      roles: authState.roles.map((name) => ({ name }))
    }
  })
}));

vi.mock("@/pages/DashboardPage", () => ({
  DashboardPage: () => <h1>Dashboard route</h1>
}));

vi.mock("@/pages/RagEvaluationsPage", () => ({
  RagEvaluationsPage: () => <h1>RAG evaluations route</h1>
}));

vi.mock("@/pages/RagEvaluationRunPage", () => ({
  RagEvaluationRunPage: () => <h1>RAG evaluation run route</h1>
}));

vi.mock("@/pages/StudentDetailPage", () => ({
  StudentDetailPage: () => <h1>Student details</h1>
}));

import { router } from "./router";

describe("router", () => {
  beforeEach(async () => {
    cleanup();
    authState.isAuthenticated = true;
    authState.isLoading = false;
    authState.status = "authenticated";
    authState.roles = ["teacher"];
    authState.sessionError = null;
    authState.login.mockReset();
    authState.logout.mockReset();
    authState.clearSessionError.mockReset();
    await router.navigate("/");
  });

  it("renders the not-found page for an authenticated user", async () => {
    await router.navigate("/settings");

    render(<RouterProvider router={router} />);

    expect(await screen.findByRole("heading", { name: /page not found/i })).toBeInTheDocument();
  });

  it.each(["/", "/simulations", "/scenarios", "/sessions", "/settings"])(
    "redirects an unauthenticated request for %s to login",
    async (path) => {
      authState.isAuthenticated = false;
      authState.status = "unauthenticated";
      await router.navigate(path);

      render(<RouterProvider router={router} />);

      await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
      expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
      expect(screen.queryByText("Operational Console")).not.toBeInTheDocument();
    }
  );

  it("shows only the session-check screen on login while a stored token is validating", async () => {
    authState.isAuthenticated = false;
    authState.isLoading = true;
    authState.status = "validating";
    await router.navigate("/login");

    render(<RouterProvider router={router} />);

    expect(await screen.findByText("Checking your session...")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Sign in" })).not.toBeInTheDocument();
    expect(screen.queryByText("Operational Console")).not.toBeInTheDocument();
  });

  it.each([
    ["teacher", "/rag-evaluations"],
    ["teacher", "/rag-evaluations/runs/11"],
    ["student", "/rag-evaluations"],
    ["student", "/rag-evaluations/runs/11"],
    ["student", "/users/alice"]
  ])("redirects %s users away from %s", async (role, path) => {
    authState.roles = [role];
    await router.navigate(path);

    render(<RouterProvider router={router} />);

    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(await screen.findByRole("heading", { name: "Dashboard route" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /rag evaluation.*route/i })).not.toBeInTheDocument();
  });

  it.each([
    ["/rag-evaluations", "RAG evaluations route"],
    ["/rag-evaluations/runs/11", "RAG evaluation run route"],
    ["/users/alice", "Student details"]
  ])("renders the admin page at %s", async (path, heading) => {
    authState.roles = ["admin"];
    await router.navigate(path);

    render(<RouterProvider router={router} />);

    await waitFor(() => expect(router.state.location.pathname).toBe(path));
    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
  });
});
