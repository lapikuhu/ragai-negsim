import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as scenarioQueries from "@/features/scenarios/scenarioQueries";

import { ScenariosPage } from "./ScenariosPage";

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
      mutateAsync: vi.fn().mockResolvedValue({
        public_context: { issue: "late checkout" },
        side_a_private_context: { goal: "avoid fee" },
        side_b_private_context: { goal: "protect policy" }
      })
    } as never);

    renderPage();

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Hotel late checkout" } });
    fireEvent.change(screen.getByLabelText("Description"), {
      target: { value: "Guest and manager discuss checkout time and fees." }
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate context" }));

    await waitFor(() => {
      expect(screen.getByLabelText("Public context JSON")).toHaveValue('{\n  "issue": "late checkout"\n}');
      expect(screen.getByLabelText("Side A private context JSON")).toHaveValue('{\n  "goal": "avoid fee"\n}');
      expect(screen.getByRole("button", { name: "Regenerate context" })).toBeInTheDocument();
    });
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
    fireEvent.click(screen.getByRole("button", { name: "Generate context" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalled());
    expect(screen.getByDisplayValue("Salary negotiation")).toBeInTheDocument();
    expect(screen.getByText("Unable to generate scenario context")).toBeInTheDocument();
  });

  it("regenerates context in edit mode without auto-saving", async () => {
    const generateMutateAsync = vi.fn().mockResolvedValue({
      public_context: { issue: "updated issue" },
      side_a_private_context: { goal: "updated side a goal" },
      side_b_private_context: { goal: "updated side b goal" }
    });

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
      mutateAsync: vi.fn()
    } as never);

    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.click(await screen.findByRole("button", { name: "Regenerate context" }));

    await waitFor(() => {
      expect(generateMutateAsync).toHaveBeenCalled();
      expect(screen.getByLabelText("Public context JSON")).toHaveValue('{\n  "issue": "updated issue"\n}');
    });
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
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
