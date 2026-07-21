import { render, screen, waitFor, within } from "@testing-library/react";
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

vi.mock("@/features/ragEvaluation/ragEvaluationQueries", () => ({
  useRagEvalConfigurationsQuery: queryMocks.configurations,
  useLatestRagEvalRuns: queryMocks.latestRuns,
  useRagEvalRunHistoryQuery: queryMocks.history,
  useCreateRagEvalConfigurationMutation: () => ({
    isPending: false,
    mutateAsync: queryMocks.create,
  }),
  useUpdateRagEvalConfigurationMutation: () => ({
    isPending: false,
    mutateAsync: queryMocks.update,
  }),
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
}));

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
});
