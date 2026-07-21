import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Sidebar } from "./Sidebar";

const authState = vi.hoisted(() => ({
  roles: [] as string[]
}));

vi.mock("@/app/AuthProvider", () => ({
  useAuth: () => ({
    hasRole: (...roles: string[]) => roles.some((role) => authState.roles.includes(role))
  })
}));

function renderSidebar() {
  return render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>
  );
}

describe("Sidebar", () => {
  beforeEach(() => {
    authState.roles = [];
  });

  it("shows the full operational console for admins", () => {
    authState.roles = ["admin"];

    renderSidebar();

    expect(screen.getByRole("link", { name: /user sessions/i })).toHaveAttribute("href", "/sessions");
    expect(screen.getByRole("link", { name: /users/i })).toHaveAttribute("href", "/users");
    expect(screen.getByRole("link", { name: /prompts/i })).toHaveAttribute("href", "/prompts");
    expect(screen.getByRole("link", { name: /rag evaluation/i })).toHaveAttribute(
      "href",
      "/rag-evaluations"
    );
    expect(screen.queryByText("Role restricted")).not.toBeInTheDocument();
  });

  it("hides admin-only sections for teachers", () => {
    authState.roles = ["teacher"];

    renderSidebar();

    expect(screen.getByRole("link", { name: /documents/i })).toHaveAttribute("href", "/documents");
    expect(screen.getByRole("link", { name: /corpora/i })).toHaveAttribute("href", "/corpora");
    expect(screen.getByRole("link", { name: /scenarios/i })).toHaveAttribute("href", "/scenarios");
    expect(screen.getByRole("link", { name: /personas/i })).toHaveAttribute("href", "/personas");
    expect(screen.getByRole("link", { name: /evaluations/i })).toHaveAttribute("href", "/evaluations");
    expect(screen.queryByText("User Sessions")).not.toBeInTheDocument();
    expect(screen.queryByText("Users")).not.toBeInTheDocument();
    expect(screen.queryByText("Prompts")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /rag evaluation/i })).not.toBeInTheDocument();
    expect(screen.queryByText("Role restricted")).not.toBeInTheDocument();
  });

  it("hides teacher and admin sections for students", () => {
    authState.roles = ["student"];

    renderSidebar();

    expect(screen.getByRole("link", { name: /dashboard/i })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: /simulations/i })).toHaveAttribute("href", "/simulations");
    expect(screen.getByRole("link", { name: /documents/i })).toHaveAttribute("href", "/documents");
    expect(screen.getByRole("link", { name: /corpora/i })).toHaveAttribute("href", "/corpora");
    expect(screen.queryByRole("link", { name: /settings/i })).not.toBeInTheDocument();
    expect(screen.queryByText("Scenarios")).not.toBeInTheDocument();
    expect(screen.queryByText("Personas")).not.toBeInTheDocument();
    expect(screen.queryByText("Evaluations")).not.toBeInTheDocument();
    expect(screen.queryByText("User Sessions")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /rag evaluation/i })).not.toBeInTheDocument();
    expect(screen.queryByText("Role restricted")).not.toBeInTheDocument();
  });
});
