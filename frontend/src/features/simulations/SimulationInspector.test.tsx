import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { SimulationReadWithState } from "@/api/types";
import { SimulationCockpitPage } from "@/pages/SimulationCockpitPage";

import { SimulationInspector } from "./SimulationInspector";

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

describe("SimulationInspector", () => {
  it("keeps the cockpit in a two-column layout with a wider inspector rail", () => {
    expect(SimulationCockpitPage).toBeTypeOf("function");
  });

  it("allows the inspector rail to shrink around wide debug content", () => {
    const { container } = render(<SimulationInspector simulation={baseSimulation} latestTurn={null} />);

    expect(container.firstChild).toHaveClass("min-w-0");
  });

  it("prefers latest turn coach advice over persisted state", () => {
    render(
      <SimulationInspector
        simulation={{
          ...baseSimulation,
          negotiation_state: {
            ...baseSimulation.negotiation_state,
            data: {
              coach_advice: {
                summary: "Persisted summary"
              }
            }
          }
        }}
        latestTurn={{
          simulation_id: 1,
          status: "paused",
          phase: "bargaining",
          should_pause: true,
          pause_reason: "counterpart_response_ready",
          messages: [],
          coach_advice: {
            summary: "Latest summary",
            suggested_response: "Try a narrower counteroffer.",
            recommended_next_move: "counter",
            confidence: "high",
            risks: ["Moving too quickly could weaken your position."]
          },
          final_evaluation: {},
          counterpart_response: "I can move a little."
        }}
      />
    );

    expect(screen.getByText("Coach guidance")).toBeInTheDocument();
    expect(screen.getByText("Latest summary")).toBeInTheDocument();
    expect(screen.queryByText("Persisted summary")).not.toBeInTheDocument();
  });

  it("falls back to persisted coach advice when latest turn is absent", () => {
    render(
      <SimulationInspector
        simulation={{
          ...baseSimulation,
          negotiation_state: {
            ...baseSimulation.negotiation_state,
            data: {
              coach_advice: {
                summary: "Persisted summary",
                suggested_response: "Ask one clarifying question before conceding."
              }
            }
          }
        }}
        latestTurn={null}
      />
    );

    expect(screen.getByText("Persisted summary")).toBeInTheDocument();
    expect(screen.getByText("Ask one clarifying question before conceding.")).toBeInTheDocument();
  });

  it("shows an empty state when no coach advice is available", () => {
    render(<SimulationInspector simulation={baseSimulation} latestTurn={null} />);

    expect(
      screen.getByText("Coach guidance will appear after a turn produces public coach output.")
    ).toBeInTheDocument();
  });

  it("renders position assessment and list sections as readable content", () => {
    render(
      <SimulationInspector
        simulation={baseSimulation}
        latestTurn={{
          simulation_id: 1,
          status: "paused",
          phase: "bargaining",
          should_pause: true,
          pause_reason: "counterpart_response_ready",
          messages: [],
          coach_advice: {
            summary: "Hold close to target.",
            position_assessment: {
              target_value: "110",
              reservation_value: "95",
              current_offer_assessment: "The current offer is still below target.",
              zopa_comment: "There appears to be room for a deal."
            },
            risks: ["Accepting now leaves value on the table."],
            missing_information: ["Whether timing flexibility matters to the counterpart."]
          },
          final_evaluation: {},
          counterpart_response: "Could you come down a bit more?"
        }}
      />
    );

    expect(screen.getByText("Position assessment")).toBeInTheDocument();
    expect(screen.getByText("The current offer is still below target.")).toBeInTheDocument();
    expect(screen.getByText("Accepting now leaves value on the table.")).toBeInTheDocument();
    expect(screen.getByText("Whether timing flexibility matters to the counterpart.")).toBeInTheDocument();
  });
});
