import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
    disableProxyMutateAsync: vi.fn(),
    learnerAskMutateAsync: vi.fn()
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
  useDisableSimulationProxyMutation: () => ({ isPending: false, mutateAsync: queryState.disableProxyMutateAsync }),
  useSimulationLearnerAskMutation: () => ({ isPending: false, mutateAsync: queryState.learnerAskMutateAsync })
}));

describe("SimulationCockpitPage", () => {
  beforeEach(() => {
    queryState.isLoading = false;
    queryState.isError = false;
    queryState.simulation = simulation;
    queryState.turnMutateAsync.mockReset();
    queryState.proxyTurnMutateAsync.mockReset();
    queryState.disableProxyMutateAsync.mockReset();
    queryState.learnerAskMutateAsync.mockReset();
  });

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
    render(<SimulationCockpitPage />);

    expect(screen.getByText("Simulation Total Tokens: 91")).toBeInTheDocument();
    expect(screen.getByLabelText("Your next turn")).toBeEnabled();
    expect(screen.getByRole("button", { name: "Send turn" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Evaluate" })).toBeDisabled();
  });

  it("hides the learner agent action when learner config is disabled", () => {
    queryState.simulation = simulation;

    render(<SimulationCockpitPage />);

    expect(screen.queryByRole("button", { name: "Ask Learning Agent" })).not.toBeInTheDocument();
  });

  it("opens a learner chat dialog and sends chat history", async () => {
    queryState.simulation = {
      ...simulation,
      negotiation_state: {
        current_phase: "bargaining",
        user_side: "side_a",
        data: {
          learner_config: { enabled: true }
        }
      }
    };
    queryState.learnerAskMutateAsync.mockResolvedValueOnce({
      simulation_id: 1,
      status: "paused",
      answer: "Hold your target and ask for objective criteria.",
      metadata: {},
      timestamp: "2026-06-10T09:01:00Z"
    });

    const user = userEvent.setup();
    render(<SimulationCockpitPage />);

    await user.click(screen.getByRole("button", { name: "Ask Learning Agent" }));

    expect(screen.getByRole("dialog", { name: "Ask Learning Agent" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hide Agent" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();

    await user.type(screen.getByLabelText("Question for learning agent"), "How should I respond?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(queryState.learnerAskMutateAsync).toHaveBeenCalledWith({
        query: "How should I respond?",
        chat_history: [{ role: "user", content: "How should I respond?" }]
      });
    });
    expect(screen.getByText("How should I respond?")).toBeInTheDocument();
    expect(screen.getByText("Hold your target and ask for objective criteria.")).toBeInTheDocument();
  });

  it("preserves learner chat while hiding and reopening the dialog", async () => {
    queryState.simulation = {
      ...simulation,
      negotiation_state: {
        current_phase: "bargaining",
        user_side: "side_a",
        data: {
          learner_config: { enabled: true }
        }
      }
    };
    queryState.learnerAskMutateAsync.mockResolvedValueOnce({
      simulation_id: 1,
      status: "paused",
      answer: "Ask for a salary-review date.",
      metadata: {},
      timestamp: "2026-06-10T09:01:00Z"
    });

    const user = userEvent.setup();
    render(<SimulationCockpitPage />);

    await user.click(screen.getByRole("button", { name: "Ask Learning Agent" }));
    await user.type(screen.getByLabelText("Question for learning agent"), "What should I ask for?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Ask for a salary-review date.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Hide Agent" }));
    expect(screen.queryByRole("dialog", { name: "Ask Learning Agent" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Ask Learning Agent" }));
    expect(screen.getByText("What should I ask for?")).toBeInTheDocument();
    expect(screen.getByText("Ask for a salary-review date.")).toBeInTheDocument();
  });

  it("shows learner ask errors inline", async () => {
    queryState.simulation = {
      ...simulation,
      negotiation_state: {
        current_phase: "bargaining",
        user_side: "side_a",
        data: {
          learner_config: { enabled: true }
        }
      }
    };
    queryState.learnerAskMutateAsync.mockRejectedValueOnce(new Error("Learning agent is not enabled"));

    const user = userEvent.setup();
    render(<SimulationCockpitPage />);

    await user.click(screen.getByRole("button", { name: "Ask Learning Agent" }));
    await user.type(screen.getByLabelText("Question for learning agent"), "Can I ask?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Learning agent is not enabled")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Ask Learning Agent" })).toBeInTheDocument();
  });

  it("renders a collapsible scenario summary before the transcript", async () => {
    queryState.isLoading = false;
    queryState.isError = false;
    queryState.simulation = {
      ...simulation,
      scenario_summary: [
        "Your target is to negotiate a stronger salary package.",
        "Keep the signing bonus private.",
        "Protect your minimum acceptable base salary.",
        "Trade vacation only for compensation.",
        "Ask for a review cycle.",
        "Do not reveal your alternative offer."
      ].join("\n")
    };

    const user = userEvent.setup();
    const { container } = render(<SimulationCockpitPage />);

    const summary = screen.getByTestId("scenario-summary-preview");
    expect(screen.getByRole("heading", { name: "Scenario summary" })).toBeInTheDocument();
    expect(summary).toHaveClass("max-h-[7.5rem]", "overflow-hidden");
    expect(screen.getByText("...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show more" })).toBeInTheDocument();

    const summaryCard = summary.closest("section");
    const transcriptHeading = screen.getByRole("heading", { name: "Transcript" });
    expect(
      summaryCard && transcriptHeading.compareDocumentPosition(summaryCard) & Node.DOCUMENT_POSITION_PRECEDING
    ).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Show more" }));

    expect(summary).not.toHaveClass("max-h-[7.5rem]");
    expect(screen.getByRole("button", { name: "Show less" })).toBeInTheDocument();
    expect(container).not.toHaveTextContent("seller floor");
  });

  it("shows the scenario summary card with an empty state when no summary is available", () => {
    queryState.isLoading = false;
    queryState.isError = false;
    queryState.simulation = {
      ...simulation,
      scenario_summary: null
    };

    render(<SimulationCockpitPage />);

    expect(screen.getByRole("heading", { name: "Scenario summary" })).toBeInTheDocument();
    expect(screen.getByText("No scenario summary is available yet.")).toBeInTheDocument();
    expect(screen.queryByTestId("scenario-summary-preview")).not.toBeInTheDocument();
  });

  it("hides the scenario summary card for simulations without a scenario", () => {
    queryState.isLoading = false;
    queryState.isError = false;
    queryState.simulation = {
      ...simulation,
      scenario_id: null,
      scenario_summary: null
    };

    render(<SimulationCockpitPage />);

    expect(screen.queryByRole("heading", { name: "Scenario summary" })).not.toBeInTheDocument();
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
