import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const authState = vi.hoisted(() => ({
  isAuthenticated: true,
  isLoading: false,
  roles: ["teacher"] as string[]
}));

vi.mock("@/app/AuthProvider", () => ({
  useAuth: () => ({
    ...authState,
    hasRole: (...roles: string[]) => roles.some((role) => authState.roles.includes(role)),
    logout: vi.fn(),
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

import { router } from "./router";

describe("router", () => {
  beforeEach(async () => {
    cleanup();
    authState.isAuthenticated = true;
    authState.isLoading = false;
    authState.roles = ["teacher"];
    await router.navigate("/");
  });

  it("renders the public not-found page for the removed settings URL", async () => {
    await router.navigate("/settings");

    render(<RouterProvider router={router} />);

    expect(await screen.findByRole("heading", { name: /page not found/i })).toBeInTheDocument();
  });

  it.each([
    ["teacher", "/rag-evaluations"],
    ["teacher", "/rag-evaluations/runs/11"],
    ["student", "/rag-evaluations"],
    ["student", "/rag-evaluations/runs/11"]
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
    ["/rag-evaluations/runs/11", "RAG evaluation run route"]
  ])("renders the admin RAG evaluation page at %s", async (path, heading) => {
    authState.roles = ["admin"];
    await router.navigate(path);

    render(<RouterProvider router={router} />);

    await waitFor(() => expect(router.state.location.pathname).toBe(path));
    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
  });
});
