import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getErrorMessage } from "@/api/client";
import { DataTable } from "@/components/common/DataTable";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { formatDateTime, toSentenceCase } from "@/utils/format";

import { useRagEvalRunHistoryQuery } from "./ragEvaluationQueries";
import { formatRagEvalProgress } from "./ragEvaluationProgress";
import type { RagEvalRunRead } from "./ragEvaluationTypes";

const historyLimit = 20;

export function RagEvaluationHistory({
  configurationId,
  configurationName,
  onClose,
}: {
  configurationId: number;
  configurationName: string;
  onClose: () => void;
}) {
  const [skip, setSkip] = useState(0);
  const history = useRagEvalRunHistoryQuery(configurationId, skip, historyLimit);

  useEffect(() => {
    setSkip(0);
  }, [configurationId]);

  const runs = useMemo(
    () =>
      [...(history.data ?? [])].sort(
        (left, right) =>
          new Date(right.queued_at).getTime() - new Date(left.queued_at).getTime(),
      ),
    [history.data],
  );

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">
            Run history: {configurationName}
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Evaluation runs are listed newest first.
          </p>
        </div>
        <Button type="button" variant="ghost" onClick={onClose}>
          Close history
        </Button>
      </div>

      <div className="mt-4">
        {history.isLoading ? (
          <LoadingState label="Loading run history..." />
        ) : history.isError ? (
          <ErrorState
            message={getErrorMessage(history.error, "Unable to load run history.")}
            onRetry={() => history.refetch()}
          />
        ) : runs.length ? (
          <DataTable
            rows={runs}
            columns={[
              {
                key: "run",
                header: "Run",
                render: (run) => (
                  <div>
                    <div className="font-medium text-slate-950">Run #{run.id}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      {formatDateTime(run.queued_at)}
                    </div>
                  </div>
                ),
              },
              {
                key: "status",
                header: "Status",
                render: (run) => <StatusBadge status={run.status} />,
              },
              {
                key: "progress",
                header: "Stage / progress",
                render: (run) => (
                  <div>
                    <div className="capitalize">{toSentenceCase(run.stage)}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      {formatRagEvalProgress(run)}
                    </div>
                  </div>
                ),
              },
              {
                key: "overall-score",
                header: "Overall score",
                render: (run) => formatMetric(run, "overall_score"),
              },
              {
                key: "hit-at-k",
                header: "Hit@K",
                render: (run) => formatMetric(run, "hit_at_k"),
              },
              {
                key: "mrr-at-k",
                header: "MRR@K",
                render: (run) => formatMetric(run, "mrr_at_k"),
              },
              {
                key: "result",
                header: "Result",
                render: (run) => (
                  <Link
                    className="font-medium text-accent hover:underline"
                    to={`/rag-evaluations/runs/${run.id}`}
                  >
                    View run {run.id}
                  </Link>
                ),
              },
            ]}
          />
        ) : (
          <EmptyState
            title="No evaluation runs"
            description="Run this configuration to create its first result."
          />
        )}
      </div>

      {!history.isLoading && !history.isError ? (
        <div className="mt-4 flex items-center justify-between gap-3">
          <Button
            type="button"
            variant="secondary"
            disabled={skip === 0}
            onClick={() => setSkip((current) => Math.max(0, current - historyLimit))}
          >
            Previous
          </Button>
          <span className="text-sm text-slate-500">
            {runs.length === 0 ? "0 runs" : `Runs ${skip + 1}–${skip + runs.length}`}
          </span>
          <Button
            type="button"
            variant="secondary"
            disabled={runs.length < historyLimit}
            onClick={() => setSkip((current) => current + historyLimit)}
          >
            Next
          </Button>
        </div>
      ) : null}
    </Card>
  );
}

function formatMetric(run: RagEvalRunRead, key: string) {
  const value = run.overall_metrics[key];
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "—";
}
