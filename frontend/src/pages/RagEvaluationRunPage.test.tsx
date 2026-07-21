import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  RagEvalQueryResultRead,
  RagEvalRunDetailRead,
} from "@/features/ragEvaluation/ragEvaluationTypes";
import { RagEvaluationRunPage } from "./RagEvaluationRunPage";

const queryMocks = vi.hoisted(() => ({ run: vi.fn() }));

vi.mock("@/features/ragEvaluation/ragEvaluationQueries", () => ({
  useRagEvalRunQuery: queryMocks.run,
}));

function makeQuery(index: number): RagEvalQueryResultRead {
  return {
    id: 100 + index,
    run_id: 11,
    example_id: `example-${String(index).padStart(2, "0")}`,
    category: index % 2 ? "direct_retrieval" : "unanswerable",
    answerable: index % 2 === 1,
    query: `Question ${index}`,
    reference_answer: `Reference answer ${index}`,
    actual_answer: `Actual answer ${index}`,
    first_relevant_rank: index === 1 ? 2 : null,
    hit_at_k: index === 1,
    mrr_at_k: index === 1 ? 0.5 : 0,
    successful_abstention: index === 1 ? false : true,
    false_positive_context: index === 1,
    faithfulness: index === 1 ? 0.91234 : 0.7,
    answer_relevancy: index === 1 ? 0.82345 : 0.7,
    context_precision: index === 1 ? 0.73456 : 0.7,
    context_recall: index === 1 ? 0.64567 : 0.7,
    answer_correctness: index === 1 ? 0.55678 : 0.7,
    final_chunks:
      index === 1
        ? [
            {
              rank: 2,
              content: "Second ranked chunk",
              metadata: {
                source: "source-b.pdf",
                score: 0.72,
                rerank_score: 0.61,
                retrieval_strategy: "vector",
                retrieval_mode: "semantic",
                evidence_path: "Entity B -> Entity C",
                chunk_index: 8,
              },
            },
            {
              rank: 1,
              content: "First ranked chunk",
              metadata: {
                source: "source-a.pdf",
                score: 0.93,
                rerank_score: 0.88,
                retrieval_strategy: "hybrid",
                retrieval_mode: "local",
                evidence_path: "Entity A -> Entity B",
                chunk_index: 3,
              },
            },
          ]
        : [],
  };
}

const completedRun: RagEvalRunDetailRead = {
  id: 11,
  configuration_id: 7,
  configuration_snapshot: {
    name: "Production CRAG",
    chunking: { strategy: "recursive", chunk_size: 800 },
    rag: { strategy: "crag", top_k: 5 },
  },
  resolved_pipeline_snapshot: {
    pipeline_version: "pipeline-v2",
    retrieval_embedding: { provider: "openai", model: "text-embedding-3-small" },
  },
  suite_version: "rag-eval-v1",
  suite_content_hash: "suite-sha-123",
  status: "completed",
  stage: "finished",
  progress: 100,
  total_examples: 12,
  completed_examples: 12,
  cancel_requested: false,
  cancellation_requested_at: null,
  overall_metrics: {
    faithfulness: 0.91234,
    guard_enabled: true,
    release_label: "stable",
  },
  category_metrics: {
    direct_retrieval: {
      context_recall: 0.87654,
      passed: false,
    },
  },
  failure_code: null,
  failure_message: null,
  queued_at: "2026-07-21T08:00:00Z",
  started_at: "2026-07-21T08:01:00Z",
  completed_at: "2026-07-21T08:10:00Z",
  query_results: Array.from({ length: 12 }, (_, index) => makeQuery(index + 1)),
};

function setRun(overrides: Partial<RagEvalRunDetailRead> = {}) {
  queryMocks.run.mockReturnValue({
    data: { ...completedRun, ...overrides },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  });
}

function renderPage(path = "/rag-evaluations/runs/11") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/rag-evaluations/runs/:runId" element={<RagEvaluationRunPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RagEvaluationRunPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setRun();
  });

  it("renders run metadata, snapshots, deterministic scalar metrics, and ten results", () => {
    renderPage();

    expect(screen.getByText("Run #11")).toBeInTheDocument();
    expect(screen.getByText("Suite rag-eval-v1")).toBeInTheDocument();
    expect(screen.getByText("Faithfulness")).toBeInTheDocument();
    expect(screen.getByText("0.912")).toBeInTheDocument();
    expect(screen.getByText("Guard Enabled")).toBeInTheDocument();
    expect(screen.getAllByText("Yes").length).toBeGreaterThan(0);
    expect(screen.getByText("Release Label")).toBeInTheDocument();
    expect(screen.getByText("stable")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Direct Retrieval" })).toBeInTheDocument();
    expect(screen.getByText("Context Recall")).toBeInTheDocument();
    expect(screen.getByText("0.877")).toBeInTheDocument();
    expect(screen.getAllByText("No").length).toBeGreaterThan(0);
    expect(screen.getByText("Production CRAG")).toBeInTheDocument();
    expect(screen.getByText("pipeline-v2")).toBeInTheDocument();
    expect(screen.getByText("suite-sha-123")).toBeInTheDocument();
    expect(screen.getByText("12 / 12")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /inspect query/i })).toHaveLength(10);
    expect(screen.getByText("example-01")).toBeInTheDocument();
    expect(screen.queryByText("example-11")).not.toBeInTheDocument();
  });

  it("filters client-side and resets ten-row pagination for every filter", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getAllByRole("button", { name: /inspect query/i })).toHaveLength(2);
    expect(screen.getByText("example-11")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeEnabled();

    await user.type(screen.getByLabelText("Search queries"), "example-01");
    expect(screen.getByText("example-01")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();

    await user.clear(screen.getByLabelText("Search queries"));
    await user.selectOptions(screen.getByLabelText("Category"), "unanswerable");
    expect(screen.getAllByRole("button", { name: /inspect query/i })).toHaveLength(6);
    expect(screen.queryByText("example-01")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Answerable"), "yes");
    expect(screen.queryByRole("button", { name: /inspect query/i })).not.toBeInTheDocument();
    expect(screen.getByText("No matching query results.")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Category"), "all");
    expect(screen.getAllByRole("button", { name: /inspect query/i })).toHaveLength(6);
    expect(screen.getByText("example-01")).toBeInTheDocument();
  });

  it("expands every query metric and complete rank-ordered chunk evidence", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Inspect query example-01" }));
    const detail = screen.getByRole("region", { name: "Evidence for example-01" });

    expect(within(detail).getByText("Reference answer 1")).toBeInTheDocument();
    expect(within(detail).getByText("Actual answer 1")).toBeInTheDocument();
    expect(within(detail).getByText("First relevant rank")).toBeInTheDocument();
    expect(within(detail).getByText("Hit at K")).toBeInTheDocument();
    expect(within(detail).getByText("MRR at K")).toBeInTheDocument();
    expect(within(detail).getByText("Successful abstention")).toBeInTheDocument();
    expect(within(detail).getByText("False positive context")).toBeInTheDocument();
    expect(within(detail).getByText("Faithfulness")).toBeInTheDocument();
    expect(within(detail).getByText("Answer relevancy")).toBeInTheDocument();
    expect(within(detail).getByText("Context precision")).toBeInTheDocument();
    expect(within(detail).getByText("Context recall")).toBeInTheDocument();
    expect(within(detail).getByText("Answer correctness")).toBeInTheDocument();
    expect(within(detail).getByText("0.500")).toBeInTheDocument();
    expect(within(detail).getByText("0.823")).toBeInTheDocument();
    expect(within(detail).getByText("0.735")).toBeInTheDocument();
    expect(within(detail).getByText("0.646")).toBeInTheDocument();
    expect(within(detail).getByText("0.557")).toBeInTheDocument();

    const firstChunk = within(detail).getByText("First ranked chunk");
    const secondChunk = within(detail).getByText("Second ranked chunk");
    expect(
      firstChunk.compareDocumentPosition(secondChunk) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(within(detail).getByText("source-a.pdf")).toBeInTheDocument();
    expect(within(detail).getByText("0.930")).toBeInTheDocument();
    expect(within(detail).getByText("0.880")).toBeInTheDocument();
    expect(within(detail).getByText("hybrid")).toBeInTheDocument();
    expect(within(detail).getByText("local")).toBeInTheDocument();
    expect(within(detail).getByText("Entity A -> Entity B")).toBeInTheDocument();
    expect(within(detail).getByText("3.000")).toBeInTheDocument();
  });

  it.each([
    ["queued", "queued", "Waiting for execution to start."],
    ["running", "evaluating", "Evaluation is in progress."],
    ["cancelled", "finished", "This run was cancelled."],
  ] as const)("renders an empty %s state", (status, stage, message) => {
    setRun({
      status,
      stage,
      overall_metrics: {},
      category_metrics: {},
      query_results: [],
      started_at: status === "queued" ? null : completedRun.started_at,
      completed_at: null,
    });
    renderPage();

    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.getByText("No query results are available for this run.")).toBeInTheDocument();
  });

  it("renders failed messages as text and the exact cleanup-blocked warning", () => {
    const unsafeFailure = '<img src=x onerror="alert(1)"> Evaluation failed safely.';
    setRun({
      status: "failed",
      stage: "finished",
      failure_code: "evaluation_failed",
      failure_message: unsafeFailure,
      overall_metrics: {},
      category_metrics: {},
      query_results: [],
    });
    const { unmount } = renderPage();

    expect(screen.getByRole("alert")).toHaveTextContent(unsafeFailure);
    expect(document.querySelector("img")).toBeNull();

    unmount();
    setRun({
      status: "running",
      stage: "cleanup_pending",
      overall_metrics: {},
      category_metrics: {},
      query_results: [],
    });
    renderPage();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Queue execution is blocked. Graph cleanup must succeed before later experiments can start. The coordinator will retry automatically; check Neo4j connectivity if this state persists.",
    );
  });

  it.each(["0", "-2", "4.5", "not-a-number"])(
    "rejects invalid run ID %s without querying",
    (runId) => {
      renderPage(`/rag-evaluations/runs/${runId}`);

      expect(screen.getByText("RAG evaluation run not found")).toBeInTheDocument();
      expect(queryMocks.run).not.toHaveBeenCalled();
    },
  );

  it("renders loading and request error states", () => {
    queryMocks.run.mockReturnValueOnce({ isLoading: true, isError: false });
    const { unmount } = renderPage();
    expect(screen.getByText("Loading RAG evaluation run...")).toBeInTheDocument();

    unmount();
    queryMocks.run.mockReturnValueOnce({
      isLoading: false,
      isError: true,
      error: new Error("Run disappeared"),
      refetch: vi.fn(),
    });
    renderPage();
    expect(screen.getByText("Run disappeared")).toBeInTheDocument();
  });
});
