import { ApiError, apiFetch } from "@/api/client";
import { getApiBaseUrl } from "@/api/clientConfig";


export async function downloadRagEvalRunSummary(runId: number) {
  const response = await apiFetch(
    `${getApiBaseUrl()}/rag-eval-runs/${runId}/export?format=csv&report=summary`,
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
    anchor.download = `rag-eval-run-${runId}-summary.csv`;
    document.body.append(anchor);
    anchor.click();
  } finally {
    anchor?.remove();
    URL.revokeObjectURL(objectUrl);
  }
}
