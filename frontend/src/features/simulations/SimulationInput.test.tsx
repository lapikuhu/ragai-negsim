import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SimulationInput } from "./SimulationInput";

const finalEvaluation = {
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
};

describe("SimulationInput", () => {
  it("renders full evaluation as plain text when revealed", () => {
    render(
      <SimulationInput
        disabled
        disabledMessage="This simulation has ended. No further turns can be sent."
        onSubmit={vi.fn()}
        canEvaluate={false}
        evaluation={finalEvaluation}
        isEvaluationVisible
        onEvaluate={vi.fn()}
      />
    );

    expect(screen.getByText("Overall score: 0.82")).toBeInTheDocument();
    expect(screen.getByText("Goal achievement: Reached a workable agreement.")).toBeInTheDocument();
    expect(screen.getByText("Strengths")).toBeInTheDocument();
    expect(screen.getByText("Held firm on salary")).toBeInTheDocument();
    expect(screen.getByText("Kept the tone collaborative")).toBeInTheDocument();
    expect(screen.getByText("Mistakes")).toBeInTheDocument();
    expect(screen.getByText("Conceded vacation days too early")).toBeInTheDocument();
    expect(screen.getByText("Reasoning: The student balanced assertiveness with flexibility.")).toBeInTheDocument();
    expect(screen.queryByText(/"overall_score"/)).not.toBeInTheDocument();
  });

  it("keeps evaluate disabled until a stored evaluation is available", () => {
    render(
      <SimulationInput
        disabled
        disabledMessage="This simulation has ended. No further turns can be sent."
        onSubmit={vi.fn()}
        canEvaluate={false}
        evaluation={null}
        isEvaluationVisible={false}
        onEvaluate={vi.fn()}
        evaluationUnavailableMessage="Final evaluation is not available for this completed simulation."
      />
    );

    expect(screen.getByRole("button", { name: "Evaluate" })).toBeDisabled();
    expect(screen.getByText("Final evaluation is not available for this completed simulation.")).toBeInTheDocument();
  });

  it("disables evaluate after revealing the stored evaluation", async () => {
    const user = userEvent.setup();
    const onEvaluate = vi.fn();

    render(
      <SimulationInput
        disabled
        disabledMessage="This simulation has ended. No further turns can be sent."
        onSubmit={vi.fn()}
        canEvaluate
        evaluation={finalEvaluation}
        isEvaluationVisible={false}
        onEvaluate={onEvaluate}
      />
    );

    await user.click(screen.getByRole("button", { name: "Evaluate" }));

    expect(onEvaluate).toHaveBeenCalledTimes(1);
  });

  it("opens the proxy dialog with neutral persona and one-turn defaults", async () => {
    const user = userEvent.setup();

    render(
      <SimulationInput
        onSubmit={vi.fn()}
        onProxySubmit={vi.fn()}
        canEvaluate={false}
        evaluation={null}
        isEvaluationVisible={false}
      />
    );

    await user.click(screen.getByRole("button", { name: "Use Proxy" }));

    expect(screen.getByRole("dialog", { name: "Use Proxy" })).toBeInTheDocument();
    expect(screen.getByLabelText("Persona")).toHaveValue("");
    expect(screen.getByLabelText("For this turn")).toBeChecked();
    expect(screen.getByLabelText("For the remainder of the negotiation")).not.toBeChecked();
  });

  it("submits the selected proxy persona and duration", async () => {
    const user = userEvent.setup();
    const onProxySubmit = vi.fn().mockResolvedValue(undefined);

    render(
      <SimulationInput
        onSubmit={vi.fn()}
        onProxySubmit={onProxySubmit}
        proxyPersonaOptions={[
          { id: 300, name: "Firm seller" },
          { id: 301, name: "Patient buyer" }
        ]}
        canEvaluate={false}
        evaluation={null}
        isEvaluationVisible={false}
      />
    );

    await user.click(screen.getByRole("button", { name: "Use Proxy" }));
    await user.selectOptions(screen.getByLabelText("Persona"), "300");
    await user.click(screen.getByLabelText("For the remainder of the negotiation"));
    await user.click(screen.getByRole("button", { name: "Confirm Proxy" }));

    expect(onProxySubmit).toHaveBeenCalledWith({ personaId: 300, duration: "remainder" });
  });

  it("closes the proxy dialog immediately after confirm while the submit is still pending", async () => {
    const user = userEvent.setup();
    let resolveSubmit: (() => void) | null = null;
    const onProxySubmit = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveSubmit = resolve;
        })
    );

    render(
      <SimulationInput
        onSubmit={vi.fn()}
        onProxySubmit={onProxySubmit}
        canEvaluate={false}
        evaluation={null}
        isEvaluationVisible={false}
      />
    );

    await user.click(screen.getByRole("button", { name: "Use Proxy" }));
    expect(screen.getByRole("dialog", { name: "Use Proxy" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Confirm Proxy" }));

    expect(onProxySubmit).toHaveBeenCalledWith({ personaId: null, duration: "this_turn" });
    expect(screen.queryByRole("dialog", { name: "Use Proxy" })).not.toBeInTheDocument();

    resolveSubmit?.();
  });
});
