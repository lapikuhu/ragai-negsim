import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as scenarioQueries from "@/features/scenarios/scenarioQueries";

import { ScenariosPage } from "./ScenariosPage";

vi.mock("@/features/llmModels/llmModelQueries", () => ({
  useLlmModelCatalogQuery: () => ({
    isLoading: false,
    isError: false,
    data: {
      providers: [
        { provider: "openai", models: [{ name: "gpt-4o-mini" }, { name: "gpt-4o" }] },
        {
          provider: "ollama",
          models: [{ name: "qwen2.5:3b", size_gib: 2.2 }],
          error: "Warmup required",
        },
      ],
      gpu_memory_gib: 8,
    },
    refetch: vi.fn(),
  }),
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
      <ScenariosPage />
    </QueryClientProvider>
  );
}

describe("ScenariosPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("generates preview JSON for create flow", async () => {
    const generateMutateAsync = vi.fn().mockResolvedValue({
      public_context: { issue: "late checkout" },
      side_a_private_context: { goal: "avoid fee" },
      side_b_private_context: { goal: "protect policy" },
      side_a_summary: "You want a later checkout without paying more.",
      side_b_summary: "You want to protect hotel policy and revenue."
    });
    vi.spyOn(scenarioQueries, "useScenariosQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      refetch: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useCreateScenarioMutation").mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useGenerateScenarioContextMutation").mockReturnValue({
      isPending: false,
      mutateAsync: generateMutateAsync
    } as never);

    renderPage();

    expect(screen.getByLabelText("Generator provider")).toHaveValue("openai");
    expect(screen.getByLabelText("Generator model")).toHaveValue("gpt-4o-mini");
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Hotel late checkout" } });
    fireEvent.change(screen.getByLabelText("Description"), {
      target: { value: "Guest and manager discuss checkout time and fees." }
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate context and summaries" }));

    await waitFor(() => {
      expect(screen.getByLabelText("Public context JSON")).toHaveValue('{\n  "issue": "late checkout"\n}');
      expect(screen.getByLabelText("Side A private context JSON")).toHaveValue('{\n  "goal": "avoid fee"\n}');
      expect(screen.getByLabelText("Side A summary")).toHaveValue("You want a later checkout without paying more.");
      expect(screen.getByLabelText("Side B summary")).toHaveValue("You want to protect hotel policy and revenue.");
      expect(screen.getByRole("button", { name: "Regenerate context and summaries" })).toBeInTheDocument();
    });
    expect(generateMutateAsync).toHaveBeenCalledWith({
      name: "Hotel late checkout",
      description: "Guest and manager discuss checkout time and fees.",
      provider: "openai",
      modelName: "gpt-4o-mini",
    });
  });

  it("sends side summaries when creating a scenario", async () => {
    const createMutateAsync = vi.fn().mockResolvedValue({});
    vi.spyOn(scenarioQueries, "useScenariosQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      refetch: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useCreateScenarioMutation").mockReturnValue({
      isPending: false,
      mutateAsync: createMutateAsync
    } as never);
    vi.spyOn(scenarioQueries, "useGenerateScenarioContextMutation").mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn()
    } as never);

    renderPage();

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Hotel late checkout" } });
    fireEvent.change(screen.getByLabelText("Description"), {
      target: { value: "Guest and manager discuss checkout time and fees." }
    });
    fireEvent.change(screen.getByLabelText("Side A summary"), {
      target: { value: "Try to get more time without a fee." }
    });
    fireEvent.change(screen.getByLabelText("Side B summary"), {
      target: { value: "Protect the policy while keeping the guest satisfied." }
    });
    fireEvent.click(screen.getByRole("button", { name: "Create scenario" }));

    await waitFor(() => {
      expect(createMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          side_a_summary: "Try to get more time without a fee.",
          side_b_summary: "Protect the policy while keeping the guest satisfied.",
        })
      );
    });
  });

  it("switches generator models when the provider changes", async () => {
    const user = userEvent.setup();
    vi.spyOn(scenarioQueries, "useScenariosQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      refetch: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useCreateScenarioMutation").mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useGenerateScenarioContextMutation").mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn()
    } as never);

    renderPage();

    await user.selectOptions(screen.getByLabelText("Generator provider"), "ollama");

    expect(screen.getByLabelText("Generator model")).toHaveValue("qwen2.5:3b");
    expect(screen.getByRole("option", { name: "qwen2.5:3b (2.2 GiB)" })).toBeInTheDocument();
    expect(screen.getByText("GPU memory: 8 GiB; Warmup required")).toBeInTheDocument();
  });

  it("keeps form input when generation fails", async () => {
    const mutateAsync = vi.fn().mockRejectedValue(new Error("Unable to generate scenario context"));
    vi.spyOn(scenarioQueries, "useScenariosQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      refetch: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useCreateScenarioMutation").mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useGenerateScenarioContextMutation").mockReturnValue({
      isPending: false,
      mutateAsync
    } as never);

    renderPage();

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Salary negotiation" } });
    fireEvent.change(screen.getByLabelText("Description"), {
      target: { value: "Candidate and recruiter discuss compensation." }
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate context and summaries" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalled());
    expect(screen.getByDisplayValue("Salary negotiation")).toBeInTheDocument();
    expect(screen.getByText("Unable to generate scenario context")).toBeInTheDocument();
  });

  it("regenerates context in edit mode without auto-saving", async () => {
    const generateMutateAsync = vi.fn().mockResolvedValue({
      public_context: { issue: "updated issue" },
      side_a_private_context: { goal: "updated side a goal" },
      side_b_private_context: { goal: "updated side b goal" },
      side_a_summary: "Updated side A summary",
      side_b_summary: "Updated side B summary"
    });
    const updateMutateAsync = vi.fn();

    vi.spyOn(scenarioQueries, "useScenariosQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        {
          id: 10,
          name: "Late checkout",
          public_context: { issue: "old issue" },
          created_by_user_id: 1,
          last_edit_by_user_id: null,
          created_at: "2026-06-09T00:00:00Z",
          last_updated: "2026-06-09T00:00:00Z",
          simulation_ids: []
        }
      ],
      refetch: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useCreateScenarioMutation").mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useGenerateScenarioContextMutation").mockReturnValue({
      isPending: false,
      mutateAsync: generateMutateAsync
    } as never);
    vi.spyOn(scenarioQueries, "useScenarioAuthoringQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        id: 10,
        name: "Late checkout",
          description: "Original description",
          public_context: { issue: "old issue" },
          side_a_private_context: { goal: "old side a goal" },
          side_b_private_context: { goal: "old side b goal" },
          side_a_summary: "Old side A summary",
          side_b_summary: "Old side B summary",
          created_by_user_id: 1,
          last_edit_by_user_id: null,
          created_at: "2026-06-09T00:00:00Z",
        last_updated: "2026-06-09T00:00:00Z",
        simulation_ids: []
      },
      refetch: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useUpdateScenarioMutation").mockReturnValue({
      isPending: false,
      mutateAsync: updateMutateAsync
    } as never);

    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    await waitFor(() => {
      const generatorModels = screen.getAllByLabelText("Generator model");
      expect(generatorModels[generatorModels.length - 1]).toHaveValue("gpt-4o-mini");
    });
    fireEvent.click(await screen.findByRole("button", { name: "Regenerate context and summaries" }));

    await waitFor(() => {
      expect(generateMutateAsync).toHaveBeenCalledWith({
        name: "Late checkout",
        description: "Original description",
        provider: "openai",
        modelName: "gpt-4o-mini",
      });
      expect(screen.getByLabelText("Public context JSON")).toHaveValue('{\n  "issue": "updated issue"\n}');
      const sideASummaries = screen.getAllByLabelText("Side A summary");
      const sideBSummaries = screen.getAllByLabelText("Side B summary");
      expect(sideASummaries[sideASummaries.length - 1]).toHaveValue("Updated side A summary");
      expect(sideBSummaries[sideBSummaries.length - 1]).toHaveValue("Updated side B summary");
    });
    expect(updateMutateAsync).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("sends side summaries when saving an edited scenario", async () => {
    const updateMutateAsync = vi.fn().mockResolvedValue({});

    vi.spyOn(scenarioQueries, "useScenariosQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        {
          id: 10,
          name: "Late checkout",
          public_context: { issue: "old issue" },
          created_by_user_id: 1,
          last_edit_by_user_id: null,
          created_at: "2026-06-09T00:00:00Z",
          last_updated: "2026-06-09T00:00:00Z",
          simulation_ids: []
        }
      ],
      refetch: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useCreateScenarioMutation").mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useGenerateScenarioContextMutation").mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useScenarioAuthoringQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        id: 10,
        name: "Late checkout",
        description: "Original description",
        public_context: { issue: "old issue" },
        side_a_private_context: { goal: "old side a goal" },
        side_b_private_context: { goal: "old side b goal" },
        side_a_summary: "Old side A summary",
        side_b_summary: "Old side B summary",
        created_by_user_id: 1,
        last_edit_by_user_id: null,
        created_at: "2026-06-09T00:00:00Z",
        last_updated: "2026-06-09T00:00:00Z",
        simulation_ids: []
      },
      refetch: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useUpdateScenarioMutation").mockReturnValue({
      isPending: false,
      mutateAsync: updateMutateAsync
    } as never);

    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    await screen.findByDisplayValue("Old side A summary");
    const sideASummaries = screen.getAllByLabelText("Side A summary");
    const sideBSummaries = screen.getAllByLabelText("Side B summary");
    fireEvent.change(sideASummaries[sideASummaries.length - 1], {
      target: { value: "Edited side A summary" }
    });
    fireEvent.change(sideBSummaries[sideBSummaries.length - 1], {
      target: { value: "Edited side B summary" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(updateMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          side_a_summary: "Edited side A summary",
          side_b_summary: "Edited side B summary",
        })
      );
    });
  });

  it("shows the first five lines of the scenario description in list view", () => {
    vi.spyOn(scenarioQueries, "useScenariosQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        {
          id: 11,
          name: "Dense context",
          description: "line 1\nline 2\nline 3\nline 4\nline 5\nline 6",
          public_context: { issue: "should not be shown" },
          created_by_user_id: 1,
          last_edit_by_user_id: null,
          created_at: "2026-06-15T00:00:00Z",
          last_updated: "2026-06-15T00:00:00Z",
          simulation_ids: []
        }
      ],
      refetch: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useCreateScenarioMutation").mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useGenerateScenarioContextMutation").mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn()
    } as never);

    renderPage();

    const preview = screen.getByTestId("scenario-description-preview");
    const label = preview.previousElementSibling;

    expect(label).toHaveTextContent("Description");
    expect(preview).toHaveTextContent("line 1");
    expect(preview).toHaveTextContent("line 5");
    expect(preview).toHaveClass("max-h-[7.5rem]");
    expect(preview).toHaveClass("overflow-hidden");
    expect(preview).not.toHaveClass("line-clamp-5");
    expect(preview).not.toHaveTextContent('"issue": "should not be shown"');
  });

  it("shows a fallback message when a scenario description is missing", () => {
    vi.spyOn(scenarioQueries, "useScenariosQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        {
          id: 12,
          name: "No description",
          description: null,
          public_context: { issue: "still hidden" },
          created_by_user_id: 1,
          last_edit_by_user_id: null,
          created_at: "2026-06-15T00:00:00Z",
          last_updated: "2026-06-15T00:00:00Z",
          simulation_ids: []
        }
      ],
      refetch: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useCreateScenarioMutation").mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn()
    } as never);
    vi.spyOn(scenarioQueries, "useGenerateScenarioContextMutation").mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn()
    } as never);

    renderPage();

    expect(screen.getByTestId("scenario-description-preview")).toHaveTextContent(
      "No description provided."
    );
  });
});
