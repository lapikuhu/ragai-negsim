import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PromptsPage } from "./PromptsPage";

const mocks = vi.hoisted(() => ({
  createPrompt: vi.fn(),
  updatePrompt: vi.fn(),
}));

vi.mock("@/features/prompts/promptQueries", () => ({
  usePromptsQuery: () => ({
    isLoading: false,
    isError: false,
    data: [
      {
        id: 10,
        name: "Coach Extension",
        description: "Extra coach behavior",
        messages: { template: "Coach with more structure." },
        owner_id: 7,
        is_system: false,
      },
    ],
    refetch: vi.fn(),
  }),
  useCreatePromptMutation: () => ({
    isPending: false,
    mutateAsync: mocks.createPrompt,
  }),
  useUpdatePromptMutation: () => ({
    isPending: false,
    mutateAsync: mocks.updatePrompt,
  }),
}));

describe("PromptsPage", () => {
  it("shows prompt template JSON copy and hides owner id fields", () => {
    render(<PromptsPage />);

    expect(screen.getAllByText("Prompt Template JSON")).toHaveLength(1);
    expect(screen.getByText(/Accepted keys: template, prompt, content, system, coach, counterpart, evaluator/)).toBeInTheDocument();
    expect(screen.getByText(/Add stricter negotiation coaching around/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Owner ID")).not.toBeInTheDocument();
  });

  it("does not submit create form when prompt template JSON is invalid", async () => {
    mocks.createPrompt.mockClear();
    render(<PromptsPage />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Invalid JSON Prompt" } });
    fireEvent.change(screen.getByLabelText("Prompt Template JSON"), { target: { value: "{invalid" } });
    fireEvent.click(screen.getByRole("button", { name: "Create prompt" }));

    expect(await screen.findByText("Prompt Template JSON must be valid JSON.")).toBeInTheDocument();
    expect(mocks.createPrompt).not.toHaveBeenCalled();
  });

  it("does not send owner id when creating a prompt", async () => {
    mocks.createPrompt.mockClear();
    render(<PromptsPage />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Valid JSON Prompt" } });
    fireEvent.change(screen.getByLabelText("Prompt Template JSON"), {
      target: { value: '{"template":"Add a custom extension."}' },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create prompt" }));

    await waitFor(() => expect(mocks.createPrompt).toHaveBeenCalled());
    expect(mocks.createPrompt.mock.calls[0][0]).toMatchObject({
      name: "Valid JSON Prompt",
      messages: { template: "Add a custom extension." },
    });
    expect(mocks.createPrompt.mock.calls[0][0]).not.toHaveProperty("owner_id");
  });
});
