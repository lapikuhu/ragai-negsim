import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "./client";
import { setAccessToken } from "./clientConfig";

describe("apiClient", () => {
  beforeEach(() => {
    setAccessToken(null);
    vi.restoreAllMocks();
  });

  it("preserves JSON content-type headers from openapi-fetch requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 2,
          name: "Updated brief",
          description: null,
          document_title: null,
          document_author: null,
          document_year: null,
          source_path: "raw/brief.pdf",
          source_hash: null,
          source_size: null,
          source_mtime: null,
          source_status: "available",
          uploaded_at: "2026-07-05T12:00:00Z",
          uploaded_by_user_id: 1,
          uploaded_by_username: "teacher",
          associated_corpora: []
        }),
        { headers: { "Content-Type": "application/json" }, status: 200 }
      )
    );

    await apiFetch(
      new Request("http://localhost/raw-documents/2", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "Updated brief" })
      })
    );

    const request = fetchMock.mock.calls[0]?.[0] as Request;
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const sentHeaders = new Headers(init.headers);

    expect(sentHeaders.get("content-type")).toBe("application/json");
    expect(await request.clone().text()).toBe(JSON.stringify({ name: "Updated brief" }));
  });
});
