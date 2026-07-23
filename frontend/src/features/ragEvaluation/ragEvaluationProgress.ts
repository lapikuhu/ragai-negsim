import type { RagEvalRunRead } from "./ragEvaluationTypes";

export function formatRagEvalProgress(run: RagEvalRunRead): string {
  if (run.status === "running" && run.stage === "scoring") {
    return `${run.completed_examples}/${run.total_examples} pipeline queries completed; scoring in progress.`;
  }

  const progress = Number.isFinite(run.progress) ? Math.round(run.progress) : 0;
  return `${progress}% · ${run.completed_examples}/${run.total_examples} examples`;
}
