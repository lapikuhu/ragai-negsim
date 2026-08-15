import { beforeEach, describe, expect, it, vi } from "vitest";
import { useQuery } from "@tanstack/react-query";

import {
  bm25JobRefetchInterval,
  corpusBm25BuildJobKeys,
  useCorpusBm25BuildJobQuery,
} from "./corpusBm25BuildJobQueries";

vi.mock("@tanstack/react-query", () => ({
  useMutation: vi.fn(),
  useQuery: vi.fn(),
  useQueryClient: vi.fn(),
}));

describe("BM25 build job polling", () => {
  beforeEach(() => {
    vi.mocked(useQuery).mockReset();
    vi.mocked(useQuery).mockReturnValue({} as never);
  });

  it("polls while a job is active", () => {
    expect(bm25JobRefetchInterval([{ status: "running" } as never])).toBe(2000);
  });

  it("stops polling when all jobs are terminal", () => {
    expect(bm25JobRefetchInterval([{ status: "completed" } as never])).toBe(false);
  });

  it("keys and polls one linked child only while it is active", () => {
    useCorpusBm25BuildJobQuery(91);
    const options = vi.mocked(useQuery).mock.calls[0]?.[0] as {
      queryKey: readonly unknown[];
      enabled: boolean;
      refetchInterval: (query: { state: { data?: { status?: string } } }) => number | false;
    };

    expect(options.queryKey).toEqual(corpusBm25BuildJobKeys.detail(91));
    expect(options.enabled).toBe(true);
    expect(options.refetchInterval({ state: { data: { status: "queued" } } })).toBe(2000);
    expect(options.refetchInterval({ state: { data: { status: "running" } } })).toBe(2000);
    expect(options.refetchInterval({ state: { data: { status: "completed" } } })).toBe(false);
  });

  it("disables the linked-child request when no child exists", () => {
    useCorpusBm25BuildJobQuery(null);
    const options = vi.mocked(useQuery).mock.calls[0]?.[0] as {
      enabled: boolean;
    };
    expect(options.enabled).toBe(false);
  });

  it("keeps observing a completed child while its parent can still roll it back", () => {
    useCorpusBm25BuildJobQuery(91, true);
    const options = vi.mocked(useQuery).mock.calls[0]?.[0] as unknown as {
      refetchInterval: (query: { state: { data?: { status?: string } } }) => number | false;
    };

    expect(options.refetchInterval({ state: { data: { status: "completed" } } })).toBe(2000);
  });
});
