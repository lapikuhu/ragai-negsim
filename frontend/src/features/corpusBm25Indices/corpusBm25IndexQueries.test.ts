import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import { listCorpusBm25Indices } from "./corpusBm25IndexQueries";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    apiClient: { GET: vi.fn() },
  };
});

describe("BM25 index metadata requests", () => {
  beforeEach(() => vi.clearAllMocks());

  it("requests built metadata for the selected corpus with bounded pagination", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: [],
      error: undefined,
      response: new Response(null, { status: 200 }),
    } as never);

    await expect(listCorpusBm25Indices(11)).resolves.toEqual([]);

    expect(apiClient.GET).toHaveBeenCalledWith("/corpus-bm25-indices/", {
      params: {
        query: { skip: 0, limit: 100, status: "built", corpus_id: 11 },
      },
    });
  });

  it("loads every metadata page so selectors do not silently stop at 100", async () => {
    const firstPage = Array.from({ length: 100 }, (_, index) => ({ id: index + 1 }));
    const secondPage = [{ id: 101 }];
    vi.mocked(apiClient.GET)
      .mockResolvedValueOnce({
        data: firstPage,
        error: undefined,
        response: new Response(null, { status: 200 }),
      } as never)
      .mockResolvedValueOnce({
        data: secondPage,
        error: undefined,
        response: new Response(null, { status: 200 }),
      } as never);

    await expect(listCorpusBm25Indices(11)).resolves.toHaveLength(101);
    expect(apiClient.GET).toHaveBeenNthCalledWith(2, "/corpus-bm25-indices/", {
      params: {
        query: { skip: 100, limit: 100, status: "built", corpus_id: 11 },
      },
    });
  });
});
