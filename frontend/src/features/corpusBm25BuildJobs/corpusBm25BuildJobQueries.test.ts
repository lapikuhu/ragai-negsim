import { describe, expect, it } from "vitest";

import { bm25JobRefetchInterval } from "./corpusBm25BuildJobQueries";

describe("BM25 build job polling", () => {
  it("polls while a job is active", () => {
    expect(bm25JobRefetchInterval([{ status: "running" } as never])).toBe(2000);
  });

  it("stops polling when all jobs are terminal", () => {
    expect(bm25JobRefetchInterval([{ status: "completed" } as never])).toBe(false);
  });
});
