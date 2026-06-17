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
  rag_profile_id: 40,
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
    data: {
      token_usage: {
        simulation_total: 91
      }
    }
  }
};

const completedSimulation: SimulationReadWithState = {
  ...simulation,
  status: "completed",
  negotiation_state: {
    current_phase: "ended",
    user_side: "side_a",
    data: {
      phase: "ended",
      token_usage: {
        simulation_total: 140,
        evaluator_total: 61
      },
      final_evaluation: {
        overall_score: 0.82,
        goal_achievement: "Reached a workable agreement.",
        strengths: ["Held firm on salary", "Kept the tone collaborative"],
        mistakes: ["Conceded vacation days too early"],
        concession_quality: "Measured and deliberate.",
        communication_quality: "Clear and professional.",
        outcome_quality: "Strong overall outcome.",
        lessons: ["Anchor earlier next time"],
        reasoning: "The student balanced assertiveness with flexibility.",
        confidence: "high",
        missing_information: ["Private reservation value was not explicit"]
      }
    }
  }
};

const completedSimulationWithoutEvaluation: SimulationReadWithState = {
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

vi.mock("@/features/counterpartPersonas/personaQueries", () => ({
  usePersonasQuery: () => ({
    data: [
      { id: 300, name: "Firm seller" },
      { id: 301, name: "Patient buyer" }
    ]
  })
}));

vi.mock("@/features/llmModels/llmModelQueries", () => ({
  useLlmModelCatalogQuery: () => ({
    isLoading: false,
    isError: false,
    data: {
      providers: [
        {
          provider: "openai",
          models: [{ name: "gpt-4o-mini" }, { name: "gpt-4.1-mini" }]
        },
        {
          provider: "ollama",
          models: [{ name: "qwen2.5:3b", size_gib: 2.3 }]
        }
      ],
      gpu_memory_gib: 12
    }
  })
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
    rag_profile_id: 40,
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
    isLoading: false,
    isError: false,
    simulation: baseSimulation,
    turnMutateAsync: vi.fn(),
    proxyTurnMutateAsync: vi.fn(),
    disableProxyMutateAsync: vi.fn()
  };
});

vi.mock("@/features/simulations/simulationQueries", () => ({
  useSimulationDetailQuery: () => ({
    isLoading: queryState.isLoading,
    isError: queryState.isError,
    data: queryState.simulation,
    error: null,
    refetch: vi.fn()
  }),
  useStartSimulationMutation: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useSimulationTurnMutation: () => ({ isPending: false, mutateAsync: queryState.turnMutateAsync }),
  useSimulationProxyTurnMutation: () => ({ isPending: false, mutateAsync: queryState.proxyTurnMutateAsync }),
  useDisableSimulationProxyMutation: () => ({ isPending: false, mutateAsync: queryState.disableProxyMutateAsync })
}));

describe("SimulationCockpitPage", () => {
  it("does not change hook order when the query moves from loading to ready", () => {
    queryState.isLoading = true;
    queryState.isError = false;
    queryState.simulation = simulation;

    const { rerender } = render(<SimulationCockpitPage />);
    expect(screen.getByText("Loading simulation...")).toBeInTheDocument();

    queryState.isLoading = false;
    rerender(<SimulationCockpitPage />);

    expect(screen.getByText("Salary negotiation")).toBeInTheDocument();
  });

  it("keeps the composer enabled for paused simulations", () => {
    queryState.isLoading = false;
    queryState.isError = false;
    queryState.simulation = simulation;
    render(<SimulationCockpitPage />);

    expect(screen.getByText("Simulation Total Tokens: 91")).toBeInTheDocument();
    expect(screen.getByLabelText("Your next turn")).toBeEnabled();
    expect(screen.getByRole("button", { name: "Send turn" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Evaluate" })).toBeDisabled();
  });

  it("enables evaluation for completed simulations with stored final evaluation", () => {
    queryState.isLoading = false;
    queryState.isError = false;
    queryState.simulation = completedSimulation;
    render(<SimulationCockpitPage />);

    expect(screen.getByLabelText("Your next turn")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send turn" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Evaluate" })).toBeEnabled();
    expect(screen.getByText("This simulation has ended. No further turns can be sent.")).toBeInTheDocument();
  });

  it("reveals the stored evaluation and disables evaluate after click", async () => {
    queryState.isLoading = false;
    queryState.isError = false;
    queryState.simulation = completedSimulation;
    const user = userEvent.setup();
    render(<SimulationCockpitPage />);

    await user.click(screen.getByRole("button", { name: "Evaluate" }));

    expect(screen.getByText("Overall score: 0.82")).toBeInTheDocument();
    expect(screen.getByText("61 total evaluator tokens")).toBeInTheDocument();
    expect(screen.getByText("Goal achievement: Reached a workable agreement.")).toBeInTheDocument();
    expect(screen.getByText("Reasoning: The student balanced assertiveness with flexibility.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Evaluate" })).toBeDisabled();
  });

  it("keeps evaluate disabled and explains when no stored evaluation exists", () => {
    queryState.isLoading = false;
    queryState.isError = false;
    queryState.simulation = completedSimulationWithoutEvaluation;
    render(<SimulationCockpitPage />);

    expect(screen.getByRole("button", { name: "Evaluate" })).toBeDisabled();
    expect(screen.getByText("Final evaluation is not available for this completed simulation.")).toBeInTheDocument();
  });

  it("locks the composer immediately after a terminal turn response", async () => {
    queryState.isLoading = false;
    queryState.isError = false;
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
    expect(screen.getByRole("button", { name: "Evaluate" })).toBeEnabled();
    expect(screen.getByText("This simulation has ended. No further turns can be sent.")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Evaluate" }));

    expect(screen.getByText("Overall score: 0.9")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Evaluate" })).toBeDisabled();
  });

  it("caps the inspector grid track while leaving the work area flexible", () => {
    queryState.isLoading = false;
    queryState.isError = false;
    queryState.simulation = simulation;
    const { container } = render(<SimulationCockpitPage />);
    const cockpitGrid = Array.from(container.querySelectorAll("div")).find((element) =>
      element.className.includes("xl:grid-cols")
    );

    expect(cockpitGrid).toHaveClass("xl:grid-cols-[minmax(0,1fr)_minmax(360px,520px)]");
  });

  it("shows persistent proxy status and a take-control action when proxy mode is enabled", () => {
    queryState.isLoading = false;
    queryState.isError = false;
    queryState.simulation = {
      ...simulation,
      negotiation_state: {
        current_phase: "bargaining",
        user_side: "side_a",
        data: {
          auto_user_proxy_enabled: true,
          user_proxy_persona: { id: 300, name: "Firm seller" }
        }
      }
    };

    render(<SimulationCockpitPage />);

    expect(screen.getByText("Proxy active: Firm seller")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Take Control" })).toBeInTheDocument();
    expect(screen.getByLabelText("Your next turn")).toBeDisabled();
  });

  it("submits a proxy turn from the dialog", async () => {
    queryState.isLoading = false;
    queryState.isError = false;
    queryState.simulation = simulation;
    queryState.proxyTurnMutateAsync.mockResolvedValueOnce({
      simulation_id: 1,
      status: "paused",
      phase: "bargaining",
      should_pause: true,
      pause_reason: "counterpart_response_ready",
      messages: [],
      coach_advice: {},
      final_evaluation: {},
      counterpart_response: "I can do 98.",
      proxy_response: "I can move to 100 if we can settle today.",
      auto_user_proxy_enabled: false,
      user_proxy_persona: { id: 300, name: "Firm seller" }
    });

    const user = userEvent.setup();
    render(<SimulationCockpitPage />);

    await user.click(screen.getByRole("button", { name: "Use Proxy" }));
    await user.selectOptions(screen.getByLabelText("Provider"), "ollama");
    await user.selectOptions(screen.getByLabelText("Model"), "qwen2.5:3b");
    await user.click(screen.getByRole("button", { name: "Confirm Proxy" }));

    await waitFor(() => {
      expect(queryState.proxyTurnMutateAsync).toHaveBeenCalledWith({
        persona_id: null,
        duration: "this_turn",
        proxy_llm_provider: "ollama",
        proxy_llm_model: "qwen2.5:3b"
      });
    });
  });

  it("disables persistent proxy mode when take control is pressed", async () => {
    queryState.isLoading = false;
    queryState.isError = false;
    queryState.simulation = {
      ...simulation,
      negotiation_state: {
        current_phase: "bargaining",
        user_side: "side_a",
        data: {
          auto_user_proxy_enabled: true,
          user_proxy_persona: { id: 300, name: "Firm seller" }
        }
      }
    };
    queryState.disableProxyMutateAsync.mockResolvedValueOnce({
      simulation_id: 1,
      status: "paused",
      auto_user_proxy_enabled: false,
      user_proxy_persona: {},
      messages: []
    });

    const user = userEvent.setup();
    render(<SimulationCockpitPage />);

    await user.click(screen.getByRole("button", { name: "Take Control" }));

    await waitFor(() => {
      expect(queryState.disableProxyMutateAsync).toHaveBeenCalledTimes(1);
    });
  });

  it("does not render the embedded teacher review form", () => {
    queryState.isLoading = false;
    queryState.isError = false;
    queryState.simulation = completedSimulation;

    render(<SimulationCockpitPage />);

    expect(screen.queryByText("Teacher review")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit review" })).not.toBeInTheDocument();
  });
});
