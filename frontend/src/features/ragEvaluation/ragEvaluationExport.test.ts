import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch } from "@/api/client";
import { downloadRagEvalRunSummary } from "./ragEvaluationExport";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, apiFetch: vi.fn() };
});

vi.mock("@/api/clientConfig", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/clientConfig")>();
  return { ...actual, getApiBaseUrl: () => "" };
});

let clickSpy: ReturnType<typeof vi.spyOn>;
let removeSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn(() => "blob:rag-eval-summary"),
    revokeObjectURL: vi.fn(),
  });
  clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  removeSpy = vi.spyOn(Element.prototype, "remove");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("RAG evaluation run summary download", () => {
  it("downloads the authenticated CSV and releases the object URL", async () => {
    const csvBlob = new Blob(["Section,Field,Value\r\n"], { type: "text/csv" });
    vi.mocked(apiFetch).mockResolvedValue(new Response(csvBlob, { status: 200 }));

    await downloadRagEvalRunSummary(11);

    expect(apiFetch).toHaveBeenCalledWith(
      "/rag-eval-runs/11/export?format=csv&report=summary",
    );
    expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
    expect(clickSpy).toHaveBeenCalledOnce();
    expect(removeSpy).toHaveBeenCalledOnce();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:rag-eval-summary");
  });

  it("uses the stable run-based filename", async () => {
    vi.mocked(apiFetch).mockResolvedValue(new Response("csv", { status: 200 }));
    let filename = "";
    clickSpy.mockImplementation(function (this: HTMLAnchorElement) {
      filename = this.download;
    });

    await downloadRagEvalRunSummary(42);

    expect(filename).toBe("rag-eval-run-42-summary.csv");
  });

  it("throws an ApiError with the server detail for a failed response", async () => {
    const detail = {
      detail: "RAG evaluation run export is available only for completed runs",
    };
    vi.mocked(apiFetch).mockResolvedValue(
      new Response(JSON.stringify(detail), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const error = await downloadRagEvalRunSummary(11).catch((reason) => reason);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, detail });
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });

  it("releases the object URL when the browser click fails", async () => {
    vi.mocked(apiFetch).mockResolvedValue(new Response("csv", { status: 200 }));
    clickSpy.mockImplementation(() => {
      throw new Error("click failed");
    });

    await expect(downloadRagEvalRunSummary(11)).rejects.toThrow("click failed");

    expect(removeSpy).toHaveBeenCalledOnce();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:rag-eval-summary");
  });

  it("releases the object URL when DOM setup fails", async () => {
    vi.mocked(apiFetch).mockResolvedValue(new Response("csv", { status: 200 }));
    vi.spyOn(document, "createElement").mockImplementationOnce(() => {
      throw new Error("DOM unavailable");
    });

    await expect(downloadRagEvalRunSummary(11)).rejects.toThrow("DOM unavailable");

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:rag-eval-summary");
  });
});
