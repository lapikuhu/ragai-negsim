import { render } from "@testing-library/react";
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

vi.mock("@/app/AuthProvider", () => ({
  useAuth: () => ({ hasRole: () => false })
}));

vi.mock("@/features/simulations/simulationQueries", () => ({
  useSimulationDetailQuery: () => ({
    isLoading: false,
    isError: false,
    data: simulation,
    error: null,
    refetch: vi.fn()
  }),
  useStartSimulationMutation: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useSimulationTurnMutation: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useReviewSimulationMutation: () => ({ isPending: false, mutateAsync: vi.fn() })
}));

describe("SimulationCockpitPage", () => {
  it("caps the inspector grid track while leaving the work area flexible", () => {
    const { container } = render(<SimulationCockpitPage />);
    const cockpitGrid = Array.from(container.querySelectorAll("div")).find((element) =>
      element.className.includes("xl:grid-cols")
    );

    expect(cockpitGrid).toHaveClass("xl:grid-cols-[minmax(0,1fr)_minmax(360px,520px)]");
  });
});
