import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "./DashboardPage";

const dashboardState = vi.hoisted(() => ({
  createData: () => ({
    simulations: [
      {
        id: 11,
        name: "Supplier negotiation",
        status: "created",
        last_updated: "2026-07-01T10:00:00Z",
      },
    ],
    documents: [
      {
        id: 21,
        name: "Course brief.pdf",
        uploaded_at: "2026-07-02T10:00:00Z",
      },
    ],
    corpora: [
      {
        id: 31,
        name: "Negotiation corpus",
        created_by_username: "admin",
        created_at: "2026-07-03T10:00:00Z",
      },
    ],
    users: [
      {
        id: 41,
        username: "learner-one",
        roles: [{ id: 2, name: "student" }],
      },
    ],
    scenarios: [
      {
        id: 51,
        name: "Vendor renewal",
        last_updated: "2026-07-04T10:00:00Z",
        simulation_ids: [11, 12],
      },
    ],
    ragProfiles: [
      {
        id: 61,
        name: "Default CRAG",
        strategy: "crag",
        last_updated: "2026-07-05T10:00:00Z",
      },
    ],
  }),
  query: {
    isLoading: false,
    isError: false,
    error: null as Error | null,
    refetch: vi.fn(),
    data: {},
  },
}));

vi.mock("@/features/dashboard/dashboardQueries", () => ({
  useDashboardQuery: () => dashboardState.query,
}));

function renderDashboard() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    dashboardState.query.data = dashboardState.createData();
  });

  it("renders recent dashboard cards without admin session activity", () => {
    renderDashboard();

    expect(screen.queryByText("Admin session activity")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start simulation" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Upload document" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Recent simulations" })).toHaveAttribute("href", "/simulations");
    expect(screen.getByText("Recent simulations")).toBeInTheDocument();
    expect(screen.getByText("Supplier negotiation")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Recent documents" })).toHaveAttribute("href", "/documents");
    expect(screen.getByText("Recent documents")).toBeInTheDocument();
    expect(screen.getByText("Course brief.pdf")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Recent corpora" })).toHaveAttribute("href", "/corpora");
    expect(screen.getByText("Recent corpora")).toBeInTheDocument();
    expect(screen.getByText("Negotiation corpus")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Users" })).toHaveAttribute("href", "/users");
    expect(screen.getByText("Users")).toBeInTheDocument();
    expect(screen.getByText("learner-one")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Recent scenarios" })).toHaveAttribute("href", "/scenarios");
    expect(screen.getByText("Recent scenarios")).toBeInTheDocument();
    expect(screen.getByText("Vendor renewal")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Recent RAG profiles" })).toHaveAttribute("href", "/rag-profiles");
    expect(screen.getByText("Recent RAG profiles")).toBeInTheDocument();
    expect(screen.getByText("Default CRAG")).toBeInTheDocument();
  });

  it("shows empty messages for the added dashboard cards", () => {
    dashboardState.query.data = {
      ...dashboardState.query.data,
      corpora: [],
      users: [],
      scenarios: [],
      ragProfiles: [],
    };

    renderDashboard();

    expect(screen.getByText("No corpora yet.")).toBeInTheDocument();
    expect(screen.getByText("No users visible.")).toBeInTheDocument();
    expect(screen.getByText("No scenarios yet.")).toBeInTheDocument();
    expect(screen.getByText("No RAG profiles yet.")).toBeInTheDocument();
  });
});
