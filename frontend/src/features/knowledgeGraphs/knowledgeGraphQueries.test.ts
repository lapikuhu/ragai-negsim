import { describe, expect, it } from "vitest";

import { getKnowledgeGraphRefetchInterval } from "./knowledgeGraphQueries";

describe("knowledge graph polling", () => {
  it("polls while a build job is active", () => {
    expect(
      getKnowledgeGraphRefetchInterval([{ status: "building", active_job_id: 3 }]),
    ).toBe(2000);
  });

  it("stops polling once all graphs are idle", () => {
    expect(
      getKnowledgeGraphRefetchInterval([{ status: "built", active_job_id: null }]),
    ).toBe(false);
  });
});
