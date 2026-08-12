import { ApiError, apiFetch } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";


export type RagEvalExportFormat = "csv" | "json";

export type RagEvalRunSummaryExport = {
  runId: number;
  format: RagEvalExportFormat;
};

export async function downloadRagEvalRunSummary(
  runId: number,
  format: RagEvalExportFormat = "csv",
) {
  const response = await apiFetch(
    `${getApiBaseUrl()}/rag-eval-runs/${runId}/export?format=${format}&report=summary`,
  );
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = undefined;
    }
    throw new ApiError(
      "Unable to export RAG evaluation run",
      response.status,
      detail,
    );
  }

  const objectUrl = URL.createObjectURL(await response.blob());
  let anchor: HTMLAnchorElement | null = null;
  try {
    anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = `rag-eval-run-${runId}-summary.${format}`;
    document.body.append(anchor);
    anchor.click();
  } finally {
    anchor?.remove();
    URL.revokeObjectURL(objectUrl);
  }
}

export function downloadRagEvalRunSummaryExport({
  runId,
  format,
}: RagEvalRunSummaryExport) {
  return downloadRagEvalRunSummary(runId, format);
}
