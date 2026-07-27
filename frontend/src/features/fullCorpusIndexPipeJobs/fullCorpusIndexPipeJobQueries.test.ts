import { beforeEach, describe, expect, it, vi } from "vitest";
import { useQuery } from "@tanstack/react-query";
import {
  useActiveFullCorpusIndexPipeJobQuery,
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
    vi.mocked(useQuery).mockReset();
    vi.mocked(useQuery).mockReturnValue({} as never);
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
});
