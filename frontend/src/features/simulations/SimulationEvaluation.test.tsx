import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SimulationEvaluation } from "./SimulationEvaluation";

describe("SimulationEvaluation", () => {
  it("shows evaluator token totals at the bottom when provided", () => {
    render(
      <SimulationEvaluation
        evaluation={{
          overall_score: 0.82,
          goal_achievement: "Reached a workable agreement.",
          strengths: ["Held firm on salary"],
          mistakes: [],
          concession_quality: "Measured",
          communication_quality: "Clear",
          outcome_quality: "Strong",
          lessons: ["Anchor earlier"],
          reasoning: "Balanced assertiveness and flexibility.",
          confidence: "high",
          missing_information: []
        }}
        evaluatorTotalTokens={61}
      />
    );

    expect(screen.getByText("61 total evaluator tokens")).toBeInTheDocument();
  });
});
