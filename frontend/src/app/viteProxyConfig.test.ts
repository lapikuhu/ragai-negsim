import { describe, expect, it } from "vitest";

import config from "../../vite.config";

describe("vite proxy config", () => {
  it("proxies rag profile and knowledge graph API routes", () => {
    const proxy = config.server?.proxy;

    expect(proxy).toBeDefined();
    expect(proxy?.["/llm-models"]).toBe("http://127.0.0.1:8000");
    expect(proxy?.["/rag-profiles"]).toBe("http://127.0.0.1:8000");
    expect(proxy?.["/knowledge-graph-indexes"]).toBe("http://127.0.0.1:8000");
    expect(proxy?.["/knowledge-graph-build-jobs"]).toBe("http://127.0.0.1:8000");
    expect(proxy?.["/document-chunks"]).toBe("http://127.0.0.1:8000");
  });
});
