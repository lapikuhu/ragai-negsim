import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { SimulationReadWithState } from "@/api/types";

import { SimulationTranscript } from "./SimulationTranscript";

const simulationWithMessage: SimulationReadWithState = {
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
  messages: [
    {
      role: "assistant",
      content: "Short reply",
      timestamp: "2026-06-10T09:00:00Z",
      metadata: {}
    }
  ],
  negotiation_state: {
    current_phase: "bargaining",
    user_side: "side_a",
    data: {}
  }
};

describe("SimulationTranscript", () => {
  it("sizes response card height to its content without changing its width", () => {
    render(<SimulationTranscript simulation={simulationWithMessage} />);

    const responseCard = screen.getByText("Short reply").closest("div");

    expect(responseCard).toHaveClass("self-start");
    expect(responseCard).not.toHaveClass("w-fit");
    expect(responseCard?.className).not.toMatch(/\bmax-w-/);
  });

  it("shows a proxy badge on proxy-authored student turns", () => {
    render(
      <SimulationTranscript
        simulation={{
          ...simulationWithMessage,
          messages: [
            {
              role: "user",
              content: "I can move to 100 if we can settle today.",
              timestamp: "2026-06-10T09:00:00Z",
              metadata: { user_reply_origin: "auto_user_proxy" }
            }
          ]
        }}
      />
    );

    expect(screen.getByText("Proxy")).toBeInTheDocument();
  });
});
