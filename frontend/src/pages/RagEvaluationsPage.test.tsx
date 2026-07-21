import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import {
  makeCragConfiguration,
  makeGraphRagConfiguration,
  type RagEvalConfigurationRead,
  type RagEvalRunRead,
} from "@/features/ragEvaluation/ragEvaluationTypes";
import { RagEvaluationsPage } from "./RagEvaluationsPage";

const queryMocks = vi.hoisted(() => ({
  configurations: vi.fn(),
  latestRuns: vi.fn(),
  history: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  enqueue: vi.fn(),
  cancel: vi.fn(),
  historyBySkip: {} as Record<number, unknown[]>,
}));

vi.mock("@/features/ragEvaluation/ragEvaluationQueries", async () => {
  const { useState } = await import("react");

  function usePendingMutation(mutation: (...args: unknown[]) => unknown) {
    const [isPending, setIsPending] = useState(false);
    return {
      isPending,
      mutateAsync: async (...args: unknown[]) => {
        setIsPending(true);
        try {
          return await mutation(...args);
        } finally {
          setIsPending(false);
        }
      },
    };
  }

  return {
    useRagEvalConfigurationsQuery: queryMocks.configurations,
    useLatestRagEvalRuns: queryMocks.latestRuns,
    useRagEvalRunHistoryQuery: queryMocks.history,
    useCreateRagEvalConfigurationMutation: () => usePendingMutation(queryMocks.create),
    useUpdateRagEvalConfigurationMutation: () => usePendingMutation(queryMocks.update),
    useDeleteRagEvalConfigurationMutation: () => ({
      isPending: false,
      mutateAsync: queryMocks.remove,
    }),
    useEnqueueRagEvalRunMutation: () => ({
      isPending: false,
      mutateAsync: queryMocks.enqueue,
    }),
    useCancelRagEvalRunMutation: () => ({
      isPending: false,
      mutateAsync: queryMocks.cancel,
    }),
  };
});

vi.mock("@/features/corpusIndices/corpusIndexQueries", () => ({
  useEmbeddingModelsQuery: () => ({
    data: [
      {
        name: "text-embedding-3-small",
        provider: "openai",
        display_name: "OpenAI text-embedding-3-small",
        dimensionality: 1536,
        normalized: false,
      },
    ],
    isLoading: false,
    isError: false,
    error: null,
  }),
}));

vi.mock("@/features/llmModels/llmModelQueries", () => ({
  useLlmModelCatalogQuery: () => ({
    data: {
      providers: [{ provider: "openai", models: [{ name: "gpt-4o-mini" }] }],
    },
    isLoading: false,
    isError: false,
    error: null,
  }),
}));

const cragInput = makeCragConfiguration();
const graphRagInput = makeGraphRagConfiguration();

const cragConfiguration: RagEvalConfigurationRead = {
  ...cragInput,
  id: 7,
  created_at: "2026-07-21T08:00:00Z",
  created_by_user_id: 1,
  last_edit_by_user_id: null,
  last_updated: "2026-07-21T09:00:00Z",
};

const graphRagConfiguration: RagEvalConfigurationRead = {
  ...graphRagInput,
  id: 9,
  created_at: "2026-07-21T08:30:00Z",
  created_by_user_id: 1,
  last_edit_by_user_id: null,
  last_updated: "2026-07-21T09:30:00Z",
};

function makeRun(
  id: number,
  configurationId: number,
  overrides: Partial<RagEvalRunRead> = {},
): RagEvalRunRead {
  return {
    id,
    configuration_id: configurationId,
    configuration_snapshot: configurationId === 7 ? cragInput : graphRagInput,
    resolved_pipeline_snapshot: {},
    suite_version: "v1",
    suite_content_hash: "hash",
    status: "completed",
    stage: "finished",
    progress: 100,
    total_examples: 80,
    completed_examples: 80,
    cancel_requested: false,
    cancellation_requested_at: null,
    overall_metrics: {
      overall_score: 0.84,
      hit_at_k: 0.75,
      mrr_at_k: 0.68,
    },
    category_metrics: {},
    failure_code: null,
    failure_message: null,
    queued_at: "2026-07-21T10:00:00Z",
    started_at: "2026-07-21T10:01:00Z",
    completed_at: "2026-07-21T10:10:00Z",
    ...overrides,
  };
}

const completedRun = makeRun(101, 7);
const cleanupPendingRun = makeRun(202, 9, {
  status: "running",
  stage: "cleanup_pending",
  progress: 96,
  completed_at: null,
});

function renderPage() {
  return render(
    <MemoryRouter>
      <RagEvaluationsPage />
    </MemoryRouter>,
  );
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("RagEvaluationsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryMocks.historyBySkip = {};
    queryMocks.configurations.mockReturnValue({
      data: [cragConfiguration, graphRagConfiguration],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    queryMocks.latestRuns.mockImplementation((ids: number[]) =>
      ids.map((id) => ({
        data: id === 7 ? completedRun : cleanupPendingRun,
        isLoading: false,
        isError: false,
        error: null,
      })),
    );
    queryMocks.history.mockImplementation(
      (_configurationId: number | null, skip: number) => ({
        data: queryMocks.historyBySkip[skip] ?? [],
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      }),
    );
    queryMocks.create.mockResolvedValue(cragConfiguration);
    queryMocks.update.mockResolvedValue(cragConfiguration);
    queryMocks.remove.mockResolvedValue(undefined);
    queryMocks.enqueue.mockResolvedValue(makeRun(303, 7, { status: "queued", stage: "queued" }));
    queryMocks.cancel.mockResolvedValue({ ...cleanupPendingRun, cancel_requested: true });
  });

  it("renders visible configurations with independent latest status, metrics, and actions", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "RAG Evaluation" })).toBeInTheDocument();
    expect(screen.getByText("CRAG experiment")).toBeInTheDocument();
    expect(screen.getByText("Overall score")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run CRAG experiment" })).toBeEnabled();
    expect(queryMocks.configurations).toHaveBeenCalledWith(0, 20);
    expect(queryMocks.latestRuns).toHaveBeenCalledWith([7, 9]);
    expect(screen.getByRole("button", { name: "Cancel GraphRAG experiment" })).toBeEnabled();
    expect(
      screen.getByRole("link", { name: "View result for CRAG experiment" }),
    ).toHaveAttribute("href", "/rag-evaluations/runs/101");
  });

  it("keeps the cleanup-pending queue warning visible", () => {
    renderPage();

    expect(screen.getByRole("alert")).toHaveTextContent("Queue execution is blocked");
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Graph cleanup must succeed before later experiments can start",
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "The coordinator will retry automatically; check Neo4j connectivity if this state persists.",
    );
  });

  it("filters history by configuration, sorts newest first, and links each result", async () => {
    const user = userEvent.setup();
    const olderRun = makeRun(111, 7, { queued_at: "2026-07-20T08:00:00Z" });
    const newerRun = makeRun(112, 7, { queued_at: "2026-07-21T08:00:00Z" });
    queryMocks.historyBySkip[0] = [olderRun, newerRun];
    renderPage();

    await user.click(screen.getByRole("button", { name: "History for CRAG experiment" }));

    expect(queryMocks.history).toHaveBeenLastCalledWith(7, 0, 20);
    const history = screen
      .getByRole("heading", { name: "Run history: CRAG experiment" })
      .closest("section");
    expect(history).not.toBeNull();
    const resultLinks = within(history as HTMLElement).getAllByRole("link", {
      name: /View run/,
    });
    expect(resultLinks[0]).toHaveAttribute("href", "/rag-evaluations/runs/112");
    expect(resultLinks[1]).toHaveAttribute("href", "/rag-evaluations/runs/111");
  });

  it("paginates history with skip and a fixed limit of 20", async () => {
    const user = userEvent.setup();
    queryMocks.historyBySkip[0] = Array.from({ length: 20 }, (_, index) =>
      makeRun(300 + index, 7, {
        queued_at: `2026-07-21T${String(index).padStart(2, "0")}:00:00Z`,
      }),
    );
    queryMocks.historyBySkip[20] = [makeRun(399, 7)];
    renderPage();
    await user.click(screen.getByRole("button", { name: "History for CRAG experiment" }));

    const history = screen
      .getByRole("heading", { name: "Run history: CRAG experiment" })
      .closest("section") as HTMLElement;
    expect(within(history).getByRole("button", { name: "Previous" })).toBeDisabled();
    await user.click(within(history).getByRole("button", { name: "Next" }));

    expect(queryMocks.history).toHaveBeenLastCalledWith(7, 20, 20);
    expect(within(history).getByRole("button", { name: "Next" })).toBeDisabled();
    await user.click(within(history).getByRole("button", { name: "Previous" }));
    expect(queryMocks.history).toHaveBeenLastCalledWith(7, 0, 20);
  });

  it("shows a zero-configuration label without an inverted range", () => {
    queryMocks.configurations.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    queryMocks.latestRuns.mockReturnValue([]);
    renderPage();

    expect(screen.getByText("0 configurations")).toBeInTheDocument();
    expect(screen.queryByText("Configurations 1–0")).not.toBeInTheDocument();
  });

  it("shows a zero-run history label without an inverted range", async () => {
    renderPage();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "History for CRAG experiment" }));
    const history = screen
      .getByRole("heading", { name: "Run history: CRAG experiment" })
      .closest("section") as HTMLElement;
    expect(within(history).getByText("0 runs")).toBeInTheDocument();
    expect(within(history).queryByText("Runs 1–0")).not.toBeInTheDocument();
  });

  it("resets history to the first page when the selected configuration changes", async () => {
    const user = userEvent.setup();
    queryMocks.historyBySkip[0] = Array.from({ length: 20 }, (_, index) =>
      makeRun(500 + index, 7),
    );
    queryMocks.historyBySkip[20] = Array.from({ length: 20 }, (_, index) =>
      makeRun(600 + index, 7),
    );
    renderPage();
    await user.click(screen.getByRole("button", { name: "History for CRAG experiment" }));

    const history = screen
      .getByRole("heading", { name: "Run history: CRAG experiment" })
      .closest("section") as HTMLElement;
    await user.click(within(history).getByRole("button", { name: "Next" }));
    expect(queryMocks.history).toHaveBeenLastCalledWith(7, 20, 20);

    await user.click(screen.getByRole("button", { name: "History for GraphRAG experiment" }));

    await waitFor(() => expect(queryMocks.history).toHaveBeenLastCalledWith(9, 0, 20));
    expect(queryMocks.history).not.toHaveBeenCalledWith(9, 20, 20);
  });

  it("wires create, edit, run, cancel, and delete feedback", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    queryMocks.remove.mockRejectedValueOnce(
      new ApiError("Unable to delete", 409, {
        detail: "Configuration is referenced by evaluation runs.",
      }),
    );
    renderPage();

    await user.click(screen.getByRole("button", { name: "Create experiment" }));
    const createDialog = screen.getByRole("dialog", { name: "Create experiment" });
    expect(createDialog).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveValue("");
    await user.type(screen.getByLabelText("Name"), "New experiment");
    await user.click(within(createDialog).getByRole("button", { name: "Create experiment" }));
    await waitFor(() => expect(queryMocks.create).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole("button", { name: "Edit CRAG experiment" }));
    expect(screen.getByLabelText("Name")).toHaveValue("CRAG experiment");
    await user.click(screen.getByRole("button", { name: "Save experiment" }));
    await waitFor(() =>
      expect(queryMocks.update).toHaveBeenCalledWith({
        id: 7,
        input: expect.objectContaining({
          name: "CRAG experiment",
          chunking: cragInput.chunking,
          rag: cragInput.rag,
          metrics: cragInput.metrics,
        }),
      }),
    );

    await user.click(screen.getByRole("button", { name: "Run CRAG experiment" }));
    expect(queryMocks.enqueue).toHaveBeenCalledWith(7);
    await user.click(screen.getByRole("button", { name: "Cancel GraphRAG experiment" }));
    expect(queryMocks.cancel).toHaveBeenCalledWith(202);

    await user.click(screen.getByRole("button", { name: "Delete CRAG experiment" }));
    expect(confirm).toHaveBeenCalledWith(
      "Delete RAG evaluation configuration \"CRAG experiment\"?",
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Configuration is referenced by evaluation runs.",
    );
    confirm.mockRestore();
  });

  it("keeps create and update failures actionable inside the editor dialog", async () => {
    const user = userEvent.setup();
    queryMocks.create.mockRejectedValueOnce(
      new ApiError("Unable to create", 409, { detail: "An experiment with this name already exists." }),
    );
    queryMocks.update.mockRejectedValueOnce(
      new ApiError("Unable to update", 409, { detail: "The experiment changed on the server." }),
    );
    renderPage();

    await user.click(screen.getByRole("button", { name: "Create experiment" }));
    let dialog = screen.getByRole("dialog", { name: "Create experiment" });
    await user.type(within(dialog).getByLabelText("Name"), "Duplicate experiment");
    await user.click(within(dialog).getByRole("button", { name: "Create experiment" }));

    let alert = await within(dialog).findByRole("alert");
    expect(alert).toHaveTextContent("An experiment with this name already exists.");
    expect(alert).toHaveTextContent("Review the configuration and try again.");
    expect(dialog).toBeInTheDocument();

    const retryCreate = within(dialog).getByRole("button", { name: "Create experiment" });
    expect(retryCreate).toBeEnabled();
    await user.click(retryCreate);
    await waitFor(() => expect(dialog).not.toBeInTheDocument());
    expect(queryMocks.create).toHaveBeenCalledTimes(2);

    await user.click(screen.getByRole("button", { name: "Edit CRAG experiment" }));
    dialog = screen.getByRole("dialog", { name: "Edit CRAG experiment" });
    await user.click(within(dialog).getByRole("button", { name: "Save experiment" }));

    alert = await within(dialog).findByRole("alert");
    expect(alert).toHaveTextContent("The experiment changed on the server.");
    expect(alert).toHaveTextContent("Review the configuration and try again.");
  });

  it("disables create and update submission while each mutation is pending", async () => {
    const createRequest = deferred<RagEvalConfigurationRead>();
    const updateRequest = deferred<RagEvalConfigurationRead>();
    queryMocks.create.mockReturnValueOnce(createRequest.promise);
    queryMocks.update.mockReturnValueOnce(updateRequest.promise);
    const user = userEvent.setup();
    const { container } = renderPage();

    await user.click(screen.getByRole("button", { name: "Create experiment" }));
    let dialog = screen.getByRole("dialog", { name: "Create experiment" });
    await user.type(within(dialog).getByLabelText("Name"), "Pending experiment");
    await user.click(within(dialog).getByRole("button", { name: "Create experiment" }));
    const createSubmit = within(dialog).getByRole("button", { name: "Create experiment" });

    await waitFor(() => expect(createSubmit).toBeDisabled());
    await user.click(createSubmit);
    expect(queryMocks.create).toHaveBeenCalledTimes(1);
    await user.keyboard("{Escape}");
    expect(dialog).toBeInTheDocument();

    createRequest.resolve(cragConfiguration);
    await waitFor(() => expect(dialog).not.toBeInTheDocument());
    expect(container).not.toHaveAttribute("inert");
    expect(container).not.toHaveAttribute("aria-hidden");
    expect(document.body).not.toHaveStyle({ overflow: "hidden" });

    await user.click(screen.getByRole("button", { name: "Edit CRAG experiment" }));
    dialog = screen.getByRole("dialog", { name: "Edit CRAG experiment" });
    await user.click(within(dialog).getByRole("button", { name: "Save experiment" }));
    const updateSubmit = within(dialog).getByRole("button", { name: "Save experiment" });

    await waitFor(() => expect(updateSubmit).toBeDisabled());
    await user.click(updateSubmit);
    expect(queryMocks.update).toHaveBeenCalledTimes(1);

    updateRequest.resolve(cragConfiguration);
    await waitFor(() => expect(dialog).not.toBeInTheDocument());
    expect(container).not.toHaveAttribute("inert");
    expect(container).not.toHaveAttribute("aria-hidden");
    expect(document.body).not.toHaveStyle({ overflow: "hidden" });
  });

  it("keeps the editor open when Escape follows submission in the same tick", async () => {
    const createRequest = deferred<RagEvalConfigurationRead>();
    queryMocks.create.mockReturnValueOnce(createRequest.promise);
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Create experiment" }));
    const dialog = screen.getByRole("dialog", { name: "Create experiment" });
    await user.type(within(dialog).getByLabelText("Name"), "Pending experiment");
    const form = dialog.querySelector("form");
    if (!form) {
      throw new Error("Expected the experiment editor form");
    }

    act(() => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });

    expect(queryMocks.create).toHaveBeenCalledTimes(1);
    expect(dialog).toBeInTheDocument();

    createRequest.resolve(cragConfiguration);
    await waitFor(() => expect(dialog).not.toBeInTheDocument());
  });

  it("makes the editor modal focus-safe, keyboard dismissible, and restores the page", async () => {
    const user = userEvent.setup();
    const { container } = renderPage();
    const opener = screen.getByRole("button", { name: "Create experiment" });

    await user.click(opener);
    const dialog = screen.getByRole("dialog", { name: "Create experiment" });
    const nameInput = within(dialog).getByLabelText("Name");
    const submit = within(dialog).getByRole("button", { name: "Create experiment" });

    expect(nameInput).toHaveFocus();
    expect(dialog).toHaveAccessibleDescription(
      "Define the chunking, retrieval, and metric settings for this experiment.",
    );
    expect(document.body).toHaveStyle({ overflow: "hidden" });
    expect(container).toHaveAttribute("inert");
    expect(container).toHaveAttribute("aria-hidden", "true");

    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(submit).toHaveFocus();
    await user.keyboard("{Tab}");
    expect(nameInput).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Create experiment" })).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
    expect(document.body).not.toHaveStyle({ overflow: "hidden" });
    expect(container).not.toHaveAttribute("inert");
    expect(container).not.toHaveAttribute("aria-hidden");
  });
});
