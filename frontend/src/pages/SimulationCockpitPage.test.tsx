import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { SimulationReadWithState } from "@/api/types";

import { SimulationCockpitPage } from "./SimulationCockpitPage";

const simulation: SimulationReadWithState = {
  id: 1,
  name: "Salary negotiation",
  description: "A negotiation simulation",
  status: "paused",
  session_id: null,
  user_id_owner: 1,
  user_id_participant: null,
  scenario_id: 10,
  corpus_id: 20,
  corpus_index_id: 30,
  coach_prompt_id: null,
  counterpart_prompt_id: null,
  evaluator_prompt_id: null,
  counter_part_side_persona_id: null,
  user_side: "side_a",
  teacher_reviewed: false,
  teacher_id: null,
  teacher_feedback: null,
  reviewed_at: null,
  created_at: "2026-06-10T09:00:00Z",
  last_updated: "2026-06-10T09:00:00Z",
  messages: [],
  negotiation_state: {
    current_phase: "bargaining",
    user_side: "side_a",
    data: {}
  }
};

const completedSimulation: SimulationReadWithState = {
  ...simulation,
  status: "completed",
  negotiation_state: {
    current_phase: "ended",
    user_side: "side_a",
    data: {
      phase: "ended"
    }
  }
};

vi.mock("@/app/AuthProvider", () => ({
  useAuth: () => ({ hasRole: () => false })
}));

const queryState = vi.hoisted(() => {
  const baseSimulation: SimulationReadWithState = {
    id: 1,
    name: "Salary negotiation",
    description: "A negotiation simulation",
    status: "paused",
    session_id: null,
    user_id_owner: 1,
    user_id_participant: null,
    scenario_id: 10,
    corpus_id: 20,
    corpus_index_id: 30,
    coach_prompt_id: null,
    counterpart_prompt_id: null,
    evaluator_prompt_id: null,
    counter_part_side_persona_id: null,
    user_side: "side_a",
    teacher_reviewed: false,
    teacher_id: null,
    teacher_feedback: null,
    reviewed_at: null,
    created_at: "2026-06-10T09:00:00Z",
    last_updated: "2026-06-10T09:00:00Z",
    messages: [],
    negotiation_state: {
      current_phase: "bargaining",
      user_side: "side_a",
      data: {}
    }
  };

  return {
    simulation: baseSimulation,
    turnMutateAsync: vi.fn()
  };
});

vi.mock("@/features/simulations/simulationQueries", () => ({
  useSimulationDetailQuery: () => ({
    isLoading: false,
    isError: false,
    data: queryState.simulation,
    error: null,
    refetch: vi.fn()
  }),
  useStartSimulationMutation: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useSimulationTurnMutation: () => ({ isPending: false, mutateAsync: queryState.turnMutateAsync }),
  useReviewSimulationMutation: () => ({ isPending: false, mutateAsync: vi.fn() })
}));

describe("SimulationCockpitPage", () => {
  it("keeps the composer enabled for paused simulations", () => {
    queryState.simulation = simulation;
    render(<SimulationCockpitPage />);

    expect(screen.getByLabelText("Your next turn")).toBeEnabled();
    expect(screen.getByRole("button", { name: "Send turn" })).toBeDisabled();
  });

  it("disables the composer and shows ended messaging for completed simulations", () => {
    queryState.simulation = completedSimulation;
    render(<SimulationCockpitPage />);

    expect(screen.getByLabelText("Your next turn")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send turn" })).toBeDisabled();
    expect(screen.getByText("This simulation has ended. No further turns can be sent.")).toBeInTheDocument();
  });

  it("locks the composer immediately after a terminal turn response", async () => {
    queryState.simulation = simulation;
    queryState.turnMutateAsync.mockResolvedValueOnce({
      simulation_id: 1,
      status: "completed",
      phase: "ended",
      should_pause: false,
      pause_reason: null,
      messages: [],
      coach_advice: {},
      final_evaluation: {
        overall_score: 0.9
      },
      counterpart_response: null
    });

    const user = userEvent.setup();
    render(<SimulationCockpitPage />);

    await user.type(screen.getByLabelText("Your next turn"), "I agree to your terms.");
    await user.click(screen.getByRole("button", { name: "Send turn" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Send turn" })).toBeDisabled();
    });
    expect(screen.getByLabelText("Your next turn")).toBeDisabled();
    expect(screen.getByText("This simulation has ended. No further turns can be sent.")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("caps the inspector grid track while leaving the work area flexible", () => {
    queryState.simulation = simulation;
    const { container } = render(<SimulationCockpitPage />);
    const cockpitGrid = Array.from(container.querySelectorAll("div")).find((element) =>
      element.className.includes("xl:grid-cols")
    );

    expect(cockpitGrid).toHaveClass("xl:grid-cols-[minmax(0,1fr)_minmax(360px,520px)]");
  });
});
