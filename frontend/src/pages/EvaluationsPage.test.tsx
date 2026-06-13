import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as simulationQueries from "@/features/simulations/simulationQueries";

import { EvaluationsPage } from "./EvaluationsPage";

vi.mock("@/app/AuthProvider", () => ({
  useAuth: () => ({
    hasRole: (...roles: string[]) => roles.includes("teacher")
  })
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <EvaluationsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("EvaluationsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders teacher review and completed sections with separate actions", () => {
    vi.spyOn(simulationQueries, "useReviewedSimulationsQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [
          {
            id: 31,
            name: "Salary negotiation",
            description: "Completed review",
            status: "completed",
            session_id: null,
            user_id_owner: 1,
            user_id_participant: 2,
            scenario_id: 100,
            corpus_id: 11,
            corpus_index_id: 77,
            coach_prompt_id: null,
            counterpart_prompt_id: null,
            evaluator_prompt_id: null,
            counter_part_side_persona_id: null,
            user_side: "side_a",
            teacher_reviewed: true,
            teacher_id: 7,
            teacher_feedback: "Strong BATNA framing",
            reviewed_at: "2026-06-10T09:00:00Z",
            created_at: "2026-06-10T09:00:00Z",
            last_updated: "2026-06-10T09:00:00Z",
            scenario_name: "Salary",
            participant_user_id: 2
          }
        ],
        skip: 0,
        limit: 20,
        has_more: false
      },
      refetch: vi.fn()
    } as never);
    vi.spyOn(simulationQueries, "useCompletedSimulationsQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [
          {
            id: 41,
            name: "Vendor negotiation",
            description: "Awaiting review",
            status: "completed",
            session_id: null,
            user_id_owner: 3,
            user_id_participant: null,
            scenario_id: 101,
            corpus_id: 12,
            corpus_index_id: 78,
            coach_prompt_id: null,
            counterpart_prompt_id: null,
            evaluator_prompt_id: null,
            counter_part_side_persona_id: null,
            user_side: "side_b",
            teacher_reviewed: false,
            teacher_id: null,
            teacher_feedback: null,
            reviewed_at: null,
            created_at: "2026-06-10T09:00:00Z",
            last_updated: "2026-06-11T09:00:00Z",
            scenario_name: "Vendor",
            participant_user_id: 3
          }
        ],
        skip: 0,
        limit: 20,
        has_more: true
      },
      refetch: vi.fn()
    } as never);
    vi.spyOn(simulationQueries, "useDeleteReviewSimulationMutation").mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn()
    } as never);

    renderPage();

    expect(screen.getByText("My Reviews")).toBeInTheDocument();
    expect(screen.getByText("Completed Simulations")).toBeInTheDocument();
    expect(screen.getByText("Strong BATNA framing")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View" })).toHaveAttribute("href", "/simulations/41");
    expect(screen.getByRole("link", { name: "Edit" })).toHaveAttribute("href", "/evaluations/31/review");
    expect(screen.getByRole("link", { name: "Review" })).toHaveAttribute("href", "/evaluations/41/review");
    expect(screen.getAllByRole("button", { name: "Previous" })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "Next" })).toHaveLength(2);
  });
});
