import { beforeEach, describe, expect, it, vi } from "vitest";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  useActiveFullCorpusIndexPipeJobQuery,
  useCreateFullCorpusIndexPipeJobMutation,
  useFullCorpusIndexPipeJobDetailQuery,
  useFullCorpusIndexPipeJobsQuery
} from "./fullCorpusIndexPipeJobQueries";

vi.mock("@tanstack/react-query", () => ({
  useMutation: vi.fn(),
  useQuery: vi.fn(),
  useQueryClient: vi.fn()
}));

describe("fullCorpusIndexPipeJobQueries polling", () => {
  beforeEach(() => {
    vi.mocked(useMutation).mockReset();
    vi.mocked(useQuery).mockReset();
    vi.mocked(useQuery).mockReturnValue({} as never);
    vi.mocked(useQueryClient).mockReset();
  });

  it("polls job history every 2s only while a full corpus index pipe job is active", () => {
    useFullCorpusIndexPipeJobsQuery(true);
    expect(vi.mocked(useQuery).mock.calls[0]?.[0]).toMatchObject({
      refetchInterval: 2000
    });

    vi.mocked(useQuery).mockClear();

    useFullCorpusIndexPipeJobsQuery(false);
    expect(vi.mocked(useQuery).mock.calls[0]?.[0]).toMatchObject({
      refetchInterval: false
    });
  });

  it("polls selected job detail every 2s only while a full corpus index pipe job is active", () => {
    useFullCorpusIndexPipeJobDetailQuery(12);
    const options = vi.mocked(useQuery).mock.calls[0]?.[0] as {
      enabled?: boolean;
      refetchInterval?: (query: { state: { data: { status?: string } | null } }) => number | false;
    };
    expect(options.enabled).toBe(true);
    expect(options.refetchInterval?.({ state: { data: { status: "running" } } })).toBe(2000);
    expect(options.refetchInterval?.({ state: { data: { status: "completed" } } })).toBe(false);
    expect(options.refetchInterval?.({ state: { data: null } })).toBe(false);
  });

  it("keeps the active job query self-governed by active statuses", () => {
    useActiveFullCorpusIndexPipeJobQuery();
    const options = vi.mocked(useQuery).mock.calls[0]?.[0] as {
      refetchInterval?: (query: { state: { data: { status?: string } | null } }) => number | false;
    };
    expect(options.refetchInterval?.({ state: { data: { status: "running" } } })).toBe(2000);
    expect(options.refetchInterval?.({ state: { data: { status: "completed" } } })).toBe(false);
    expect(options.refetchInterval?.({ state: { data: null } })).toBe(false);
  });

  it("cancels this corpus chunk-set availability request before queueing", async () => {
    const cancelQueries = vi.fn().mockResolvedValue(undefined);
    const invalidateQueries = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useQueryClient).mockReturnValue({
      cancelQueries,
      invalidateQueries,
    } as never);
    vi.mocked(useMutation).mockReturnValue({} as never);

    useCreateFullCorpusIndexPipeJobMutation();
    const options = vi.mocked(useMutation).mock.calls[0]?.[0] as {
      onMutate: (input: { corpus_id: number }) => Promise<void>;
    };

    await options.onMutate({ corpus_id: 7 });

    expect(cancelQueries).toHaveBeenCalledWith({
      queryKey: ["corpora", 7, "chunk-set-name-availability"],
    });
  });
});
