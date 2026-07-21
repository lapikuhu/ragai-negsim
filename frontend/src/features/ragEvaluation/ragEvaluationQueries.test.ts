import { createElement, type PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import {
  getRagEvalRunRefetchInterval,
  ragEvaluationKeys,
  useCancelRagEvalRunMutation,
  useCreateRagEvalConfigurationMutation,
  useDeleteRagEvalConfigurationMutation,
  useEnqueueRagEvalRunMutation,
  useLatestRagEvalRuns,
  useRagEvalConfigurationQuery,
  useRagEvalConfigurationsQuery,
  useRagEvalRunHistoryQuery,
  useRagEvalRunQuery,
  useUpdateRagEvalConfigurationMutation,
} from "./ragEvaluationQueries";
import {
  makeCragConfiguration,
  type RagEvalConfigurationInput,
  type RagEvalConfigurationRead,
  type RagEvalRunDetailRead,
  type RagEvalRunRead,
} from "./ragEvaluationTypes";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    apiClient: {
      GET: vi.fn(),
      POST: vi.fn(),
      PATCH: vi.fn(),
      DELETE: vi.fn(),
    },
  };
});

const configurationInput = makeCragConfiguration();

const configuration: RagEvalConfigurationRead = {
  ...configurationInput,
  id: 7,
  created_at: "2026-07-21T08:00:00Z",
  created_by_user_id: 1,
  last_edit_by_user_id: null,
  last_updated: "2026-07-21T08:00:00Z",
};

const queuedRun: RagEvalRunRead = {
  id: 11,
  configuration_id: 7,
  configuration_snapshot: configurationInput,
  resolved_pipeline_snapshot: {},
  suite_version: "v1",
  suite_content_hash: "hash",
  status: "queued",
  stage: "queued",
  progress: 0,
  total_examples: 80,
  completed_examples: 0,
  cancel_requested: false,
  cancellation_requested_at: null,
  overall_metrics: {},
  category_metrics: {},
  failure_code: null,
  failure_message: null,
  queued_at: "2026-07-21T08:00:00Z",
  started_at: null,
  completed_at: null,
};

const runDetail: RagEvalRunDetailRead = {
  ...queuedRun,
  query_results: [],
};

const completedRun: RagEvalRunRead = {
  ...queuedRun,
  status: "completed",
  stage: "finished",
  progress: 100,
  completed_examples: 80,
  completed_at: "2026-07-21T08:10:00Z",
};

const completedRunDetail: RagEvalRunDetailRead = {
  ...completedRun,
  query_results: [],
};

function apiResult<T>(data: T, status = 200) {
  return { data, response: new Response(null, { status }) };
}

function createHarness() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const wrapper = ({ children }: PropsWithChildren) =>
    createElement(QueryClientProvider, { client }, children);
  return { client, wrapper };
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("RAG evaluation requests", () => {
  it("requests the configuration page and configuration detail", async () => {
    vi.mocked(apiClient.GET)
      .mockResolvedValueOnce(apiResult([configuration]) as never)
      .mockResolvedValueOnce(apiResult(configuration) as never);
    const { wrapper } = createHarness();

    const list = renderHook(() => useRagEvalConfigurationsQuery(20, 10), { wrapper });
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true));
    const detail = renderHook(() => useRagEvalConfigurationQuery(7), { wrapper });
    await waitFor(() => expect(detail.result.current.isSuccess).toBe(true));

    expect(apiClient.GET).toHaveBeenNthCalledWith(1, "/rag-eval-configurations/", {
      params: { query: { skip: 20, limit: 10 } },
    });
    expect(apiClient.GET).toHaveBeenNthCalledWith(2, "/rag-eval-configurations/{id}", {
      params: { path: { id: 7 } },
    });
  });

  it("requests one filtered latest run for every visible configuration", async () => {
    vi.mocked(apiClient.GET)
      .mockResolvedValueOnce(apiResult([queuedRun]) as never)
      .mockResolvedValueOnce(apiResult([]) as never);
    const { wrapper } = createHarness();

    const latest = renderHook(() => useLatestRagEvalRuns([7, 9]), { wrapper });
    await waitFor(() => expect(latest.result.current.every((query) => query.isSuccess)).toBe(true));

    expect(apiClient.GET).toHaveBeenCalledTimes(2);
    expect(apiClient.GET).toHaveBeenCalledWith("/rag-eval-runs/", {
      params: { query: { configuration_id: 7, skip: 0, limit: 1 } },
    });
    expect(apiClient.GET).toHaveBeenCalledWith("/rag-eval-runs/", {
      params: { query: { configuration_id: 9, skip: 0, limit: 1 } },
    });
    expect(latest.result.current[0].data).toEqual(queuedRun);
    expect(latest.result.current[1].data).toBeNull();
  });

  it("requests filtered paginated history and run detail", async () => {
    vi.mocked(apiClient.GET)
      .mockResolvedValueOnce(apiResult([queuedRun]) as never)
      .mockResolvedValueOnce(apiResult(runDetail) as never);
    const { wrapper } = createHarness();

    const history = renderHook(() => useRagEvalRunHistoryQuery(7, 10, 5), { wrapper });
    await waitFor(() => expect(history.result.current.isSuccess).toBe(true));
    const detail = renderHook(() => useRagEvalRunQuery(11), { wrapper });
    await waitFor(() => expect(detail.result.current.isSuccess).toBe(true));

    expect(apiClient.GET).toHaveBeenNthCalledWith(1, "/rag-eval-runs/", {
      params: { query: { configuration_id: 7, skip: 10, limit: 5 } },
    });
    expect(apiClient.GET).toHaveBeenNthCalledWith(2, "/rag-eval-runs/{id}", {
      params: { path: { id: 11 } },
    });
  });
});

describe("RAG evaluation polling", () => {
  it("polls queued and running runs, including cleanup pending", () => {
    expect(getRagEvalRunRefetchInterval({ status: "queued", stage: "queued" })).toBe(2000);
    expect(
      getRagEvalRunRefetchInterval({ status: "running", stage: "cleanup_pending" }),
    ).toBe(2000);
  });

  it("does not poll terminal or absent runs", () => {
    expect(getRagEvalRunRefetchInterval({ status: "completed", stage: "finished" })).toBe(false);
    expect(getRagEvalRunRefetchInterval(null)).toBe(false);
  });

  it("schedules latest-run polling every two seconds and stops after a terminal response", async () => {
    vi.useFakeTimers();
    vi.mocked(apiClient.GET)
      .mockResolvedValueOnce(apiResult([queuedRun]) as never)
      .mockResolvedValueOnce(apiResult([completedRun]) as never);
    const { client, wrapper } = createHarness();
    const latest = renderHook(() => useLatestRagEvalRuns([7]), { wrapper });

    await act(async () => vi.advanceTimersByTimeAsync(0));
    expect(apiClient.GET).toHaveBeenCalledTimes(1);
    expect(latest.result.current[0].data?.status).toBe("queued");

    await act(async () => vi.advanceTimersByTimeAsync(2000));
    await act(async () => vi.advanceTimersByTimeAsync(0));
    expect(apiClient.GET).toHaveBeenCalledTimes(2);

    await act(async () => vi.advanceTimersByTimeAsync(4000));
    expect(apiClient.GET).toHaveBeenCalledTimes(2);

    latest.unmount();
    client.clear();
  });

  it("schedules run-detail polling every two seconds and stops after a terminal response", async () => {
    vi.useFakeTimers();
    vi.mocked(apiClient.GET)
      .mockResolvedValueOnce(apiResult(runDetail) as never)
      .mockResolvedValueOnce(apiResult(completedRunDetail) as never);
    const { client, wrapper } = createHarness();
    const detail = renderHook(() => useRagEvalRunQuery(11), { wrapper });

    await act(async () => vi.advanceTimersByTimeAsync(0));
    expect(apiClient.GET).toHaveBeenCalledTimes(1);
    expect(detail.result.current.data?.status).toBe("queued");

    await act(async () => vi.advanceTimersByTimeAsync(2000));
    await act(async () => vi.advanceTimersByTimeAsync(0));
    expect(apiClient.GET).toHaveBeenCalledTimes(2);

    await act(async () => vi.advanceTimersByTimeAsync(4000));
    expect(apiClient.GET).toHaveBeenCalledTimes(2);

    detail.unmount();
    client.clear();
  });

  it("polls active run history and stops when every returned row is terminal", async () => {
    vi.useFakeTimers();
    vi.mocked(apiClient.GET)
      .mockResolvedValueOnce(apiResult([completedRun, queuedRun]) as never)
      .mockResolvedValueOnce(apiResult([completedRun]) as never);
    const { client, wrapper } = createHarness();
    const history = renderHook(() => useRagEvalRunHistoryQuery(7, 0, 20), { wrapper });

    await act(async () => vi.advanceTimersByTimeAsync(0));
    expect(apiClient.GET).toHaveBeenCalledTimes(1);
    expect(history.result.current.data?.some((run) => run.status === "queued")).toBe(true);

    await act(async () => vi.advanceTimersByTimeAsync(2000));
    await act(async () => vi.advanceTimersByTimeAsync(0));
    expect(apiClient.GET).toHaveBeenCalledTimes(2);

    await act(async () => vi.advanceTimersByTimeAsync(4000));
    expect(apiClient.GET).toHaveBeenCalledTimes(2);

    history.unmount();
    client.clear();
  });
});

describe("RAG evaluation mutations", () => {
  it("creates and invalidates configuration list and detail keys", async () => {
    vi.mocked(apiClient.POST).mockResolvedValue(apiResult(configuration, 201) as never);
    const { client, wrapper } = createHarness();
    const invalidate = vi.spyOn(client, "invalidateQueries").mockResolvedValue();
    const mutation = renderHook(() => useCreateRagEvalConfigurationMutation(), { wrapper });

    await mutation.result.current.mutateAsync(configurationInput);

    expect(apiClient.POST).toHaveBeenCalledWith("/rag-eval-configurations/", {
      body: configurationInput,
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["rag-eval-configurations"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ragEvaluationKeys.configuration(7) });
  });

  it("updates and invalidates configuration list and detail keys", async () => {
    const input: RagEvalConfigurationInput = { ...configurationInput, name: "Updated" };
    vi.mocked(apiClient.PATCH).mockResolvedValue(
      apiResult({ ...configuration, name: input.name }) as never,
    );
    const { client, wrapper } = createHarness();
    const invalidate = vi.spyOn(client, "invalidateQueries").mockResolvedValue();
    const mutation = renderHook(() => useUpdateRagEvalConfigurationMutation(), { wrapper });

    await mutation.result.current.mutateAsync({ id: 7, input });

    expect(apiClient.PATCH).toHaveBeenCalledWith("/rag-eval-configurations/{id}", {
      params: { path: { id: 7 } },
      body: input,
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["rag-eval-configurations"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ragEvaluationKeys.configuration(7) });
  });

  it("deletes and invalidates configuration, latest-run, and history keys", async () => {
    vi.mocked(apiClient.DELETE).mockResolvedValue({ response: new Response(null, { status: 204 }) } as never);
    const { client, wrapper } = createHarness();
    const invalidate = vi.spyOn(client, "invalidateQueries").mockResolvedValue();
    const mutation = renderHook(() => useDeleteRagEvalConfigurationMutation(), { wrapper });

    await mutation.result.current.mutateAsync(7);

    expect(apiClient.DELETE).toHaveBeenCalledWith("/rag-eval-configurations/{id}", {
      params: { path: { id: 7 } },
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["rag-eval-configurations"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ragEvaluationKeys.configuration(7) });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ragEvaluationKeys.latestRun(7) });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["rag-eval-run-history", 7] });
  });

  it("enqueues and invalidates latest-run, history, and returned detail keys", async () => {
    vi.mocked(apiClient.POST).mockResolvedValue(apiResult(queuedRun, 202) as never);
    const { client, wrapper } = createHarness();
    const invalidate = vi.spyOn(client, "invalidateQueries").mockResolvedValue();
    const mutation = renderHook(() => useEnqueueRagEvalRunMutation(), { wrapper });

    await mutation.result.current.mutateAsync(7);

    expect(apiClient.POST).toHaveBeenCalledWith("/rag-eval-runs/", {
      body: { configuration_id: 7 },
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ragEvaluationKeys.latestRun(7) });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["rag-eval-run-history", 7] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ragEvaluationKeys.run(11) });
  });

  it("cancels and invalidates latest-run, history, and detail keys", async () => {
    vi.mocked(apiClient.POST).mockResolvedValue(
      apiResult({ ...queuedRun, cancel_requested: true }) as never,
    );
    const { client, wrapper } = createHarness();
    const invalidate = vi.spyOn(client, "invalidateQueries").mockResolvedValue();
    const mutation = renderHook(() => useCancelRagEvalRunMutation(), { wrapper });

    await mutation.result.current.mutateAsync(11);

    expect(apiClient.POST).toHaveBeenCalledWith("/rag-eval-runs/{id}/cancel", {
      params: { path: { id: 11 } },
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ragEvaluationKeys.latestRun(7) });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["rag-eval-run-history", 7] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ragEvaluationKeys.run(11) });
  });
});
