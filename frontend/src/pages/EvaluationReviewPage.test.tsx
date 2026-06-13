import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as simulationQueries from "@/features/simulations/simulationQueries";

import { EvaluationReviewPage } from "./EvaluationReviewPage";

vi.mock("@/app/AuthProvider", () => ({
  useAuth: () => ({
    user: { id: 7 },
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
      <MemoryRouter initialEntries={["/evaluations/31/review"]}>
        <Routes>
          <Route path="/evaluations/:simulationId/review" element={<EvaluationReviewPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("EvaluationReviewPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("prefills an existing review and submits an update", async () => {
    const patchMutateAsync = vi.fn().mockResolvedValue(undefined);
    vi.spyOn(simulationQueries, "useSimulationDetailQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        id: 31,
        name: "Salary negotiation",
        description: "Completed simulation",
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
        teacher_feedback: "Initial review",
        reviewed_at: "2026-06-10T09:00:00Z",
        created_at: "2026-06-10T09:00:00Z",
        last_updated: "2026-06-10T10:00:00Z",
        messages: [],
        negotiation_state: {
          current_phase: "ended",
          user_side: "side_a",
          data: {}
        }
      },
      refetch: vi.fn()
    } as never);
    vi.spyOn(simulationQueries, "useUpdateReviewSimulationMutation").mockReturnValue({
      isPending: false,
      mutateAsync: patchMutateAsync
    } as never);
    vi.spyOn(simulationQueries, "useReviewSimulationMutation").mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn()
    } as never);

    renderPage();

    expect(screen.getByDisplayValue("Initial review")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Teacher Review"), { target: { value: "Updated review" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(patchMutateAsync).toHaveBeenCalledWith({ teacher_feedback: "Updated review" });
    });
  });
});
