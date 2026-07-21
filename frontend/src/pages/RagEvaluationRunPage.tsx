import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { getErrorMessage } from "@/api/client";
import { ErrorState } from "@/components/common/ErrorState";
import { KeyValueList } from "@/components/common/KeyValueList";
import { LoadingState } from "@/components/common/LoadingState";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useRagEvalRunQuery } from "@/features/ragEvaluation/ragEvaluationQueries";
import type {
  RagEvalQueryResultRead,
  RagEvalRunDetailRead,
} from "@/features/ragEvaluation/ragEvaluationTypes";
import { formatDateTime } from "@/utils/format";

const pageSize = 10;
const cleanupBlockedMessage =
  "Queue execution is blocked. Graph cleanup must succeed before later experiments can start. The coordinator will retry automatically; check Neo4j connectivity if this state persists.";

export function RagEvaluationRunPage() {
  const runId = Number(useParams().runId);

  if (!Number.isInteger(runId) || runId <= 0) {
    return (
      <ErrorState
        title="RAG evaluation run not found"
        message="The requested run ID must be a positive integer."
      />
    );
  }

  return <RagEvaluationRunDetail runId={runId} />;
}

function RagEvaluationRunDetail({ runId }: { runId: number }) {
  const runQuery = useRagEvalRunQuery(runId);

  if (runQuery.isLoading) {
    return <LoadingState label="Loading RAG evaluation run..." />;
  }

  if (runQuery.isError) {
    return (
      <ErrorState
        title="Unable to load RAG evaluation run"
        message={getErrorMessage(runQuery.error, "Unable to load RAG evaluation run.")}
        onRetry={() => runQuery.refetch()}
      />
    );
  }

  if (!runQuery.data) {
    return (
      <ErrorState
        title="RAG evaluation run not found"
        message="No run was returned for the requested ID."
      />
    );
  }

  return <RunContent run={runQuery.data} />;
}

function RunContent({ run }: { run: RagEvalRunDetailRead }) {
  return (
    <div className="grid gap-6">
      <PageHeader title={`Run #${run.id}`} description={`Suite ${run.suite_version}`} />

      {run.stage === "cleanup_pending" ? (
        <div
          role="alert"
          className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950"
        >
          {cleanupBlockedMessage}
        </div>
      ) : null}

      {run.status === "failed" ? (
        <div
          role="alert"
          className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-900"
        >
          <strong>{run.failure_code ? `${humanizeMetric(run.failure_code)}: ` : ""}</strong>
          {run.failure_message ?? "The evaluation failed without a message."}
        </div>
      ) : null}

      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-950">Run status</h2>
          <StatusBadge status={run.status} />
        </div>
        <KeyValueList
          items={[
            { label: "Stage", value: humanizeMetric(run.stage) },
            { label: "Progress", value: `${formatProgress(run.progress)}%` },
            {
              label: "Examples completed",
              value: `${run.completed_examples} / ${run.total_examples}`,
            },
            { label: "Queued at", value: formatDateTime(run.queued_at) },
            { label: "Started at", value: formatDateTime(run.started_at) },
            { label: "Completed at", value: formatDateTime(run.completed_at) },
            { label: "Cancel requested", value: run.cancel_requested ? "Yes" : "No" },
            {
              label: "Cancellation requested at",
              value: formatDateTime(run.cancellation_requested_at),
            },
            { label: "Suite version", value: run.suite_version },
            { label: "Suite content hash", value: run.suite_content_hash },
            { label: "Configuration ID", value: run.configuration_id },
          ]}
        />
        <RunStateMessage run={run} />
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <SnapshotCard title="Configuration snapshot" value={run.configuration_snapshot} />
        <SnapshotCard
          title="Resolved pipeline snapshot"
          value={run.resolved_pipeline_snapshot}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <h2 className="text-lg font-semibold text-slate-950">Overall metrics</h2>
          <div className="mt-4">
            <MetricList metrics={run.overall_metrics} />
          </div>
        </Card>
        <Card>
          <h2 className="text-lg font-semibold text-slate-950">Category metrics</h2>
          <div className="mt-4 grid gap-4">
            {metricEntries(run.category_metrics).length ? (
              metricEntries(run.category_metrics).map(([category, value]) => (
                <section key={category} className="rounded-xl border border-slate-200 p-4">
                  <h3 className="font-medium text-slate-950">{humanizeMetric(category)}</h3>
                  <div className="mt-3">
                    {isRecord(value) ? (
                      <MetricList metrics={value} />
                    ) : (
                      <span className="text-sm text-slate-700">{formatScalar(value)}</span>
                    )}
                  </div>
                </section>
              ))
            ) : (
              <p className="text-sm text-slate-600">No category metrics are available.</p>
            )}
          </div>
        </Card>
      </div>

      <QueryEvidence queryResults={run.query_results ?? []} />
    </div>
  );
}

function RunStateMessage({ run }: { run: RagEvalRunDetailRead }) {
  let message: string | null = null;
  if (run.status === "queued") {
    message = "Waiting for execution to start.";
  } else if (run.status === "running" && run.stage !== "cleanup_pending") {
    message = "Evaluation is in progress.";
  } else if (run.status === "cancelled") {
    message = "This run was cancelled.";
  }

  return message ? <p className="mt-4 text-sm text-slate-600">{message}</p> : null;
}

function SnapshotCard({ title, value }: { title: string; value: Record<string, unknown> }) {
  const entries = flattenSnapshot(value);
  return (
    <Card>
      <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
      {entries.length ? (
        <dl className="mt-4 grid gap-2">
          {entries.map(([path, leaf]) => (
            <div key={path} className="rounded-xl bg-slate-50 px-3 py-2">
              <dt className="text-xs uppercase tracking-wide text-slate-500">
                {path.split(".").map(humanizeMetric).join(" / ")}
              </dt>
              <dd className="mt-1 break-words text-sm text-slate-900">
                {formatScalar(leaf)}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="mt-4 text-sm text-slate-600">No snapshot data is available.</p>
      )}
    </Card>
  );
}

function QueryEvidence({ queryResults }: { queryResults: RagEvalQueryResultRead[] }) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [answerable, setAnswerable] = useState("all");
  const [page, setPage] = useState(0);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const categories = useMemo(
    () => [...new Set(queryResults.map((result) => result.category))].sort(),
    [queryResults],
  );
  const filteredResults = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    return queryResults.filter((result) => {
      const searchable = [
        result.example_id,
        result.query,
        result.reference_answer ?? "",
        result.actual_answer,
      ];
      const matchesSearch =
        !needle || searchable.some((value) => value.toLocaleLowerCase().includes(needle));
      const matchesCategory = category === "all" || result.category === category;
      const matchesAnswerable =
        answerable === "all" || result.answerable === (answerable === "yes");
      return matchesSearch && matchesCategory && matchesAnswerable;
    });
  }, [answerable, category, queryResults, search]);
  const pageCount = Math.max(1, Math.ceil(filteredResults.length / pageSize));
  const currentPage = Math.min(page, pageCount - 1);
  const visibleResults = filteredResults.slice(
    currentPage * pageSize,
    currentPage * pageSize + pageSize,
  );

  function resetPage() {
    setPage(0);
  }

  function toggleExpanded(id: number) {
    setExpandedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <Card>
      <h2 className="text-lg font-semibold text-slate-950">Query evidence</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <label className="grid gap-1 text-sm text-slate-700">
          Search queries
          <input
            className="rounded-lg border border-slate-300 px-3 py-2"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              resetPage();
            }}
          />
        </label>
        <label className="grid gap-1 text-sm text-slate-700">
          Category
          <select
            className="rounded-lg border border-slate-300 px-3 py-2"
            value={category}
            onChange={(event) => {
              setCategory(event.target.value);
              resetPage();
            }}
          >
            <option value="all">All categories</option>
            {categories.map((value) => (
              <option key={value} value={value}>
                {humanizeMetric(value)}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-slate-700">
          Answerable
          <select
            className="rounded-lg border border-slate-300 px-3 py-2"
            value={answerable}
            onChange={(event) => {
              setAnswerable(event.target.value);
              resetPage();
            }}
          >
            <option value="all">All</option>
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </select>
        </label>
      </div>

      <div className="mt-5 grid gap-4">
        {visibleResults.length ? (
          visibleResults.map((result) => (
            <article key={result.id} className="rounded-xl border border-slate-200 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="font-medium text-slate-950">{result.example_id}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {humanizeMetric(result.category)} · Answerable {result.answerable ? "Yes" : "No"}
                  </div>
                  <p className="mt-2 text-sm text-slate-700">{result.query}</p>
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  aria-expanded={expandedIds.has(result.id)}
                  onClick={() => toggleExpanded(result.id)}
                >
                  {expandedIds.has(result.id) ? "Hide" : "Inspect"} query {result.example_id}
                </Button>
              </div>
              {expandedIds.has(result.id) ? <QueryResultDetail result={result} /> : null}
            </article>
          ))
        ) : (
          <p className="text-sm text-slate-600">
            {queryResults.length
              ? "No matching query results."
              : "No query results are available for this run."}
          </p>
        )}
      </div>

      <div className="mt-5 flex items-center justify-between gap-3">
        <Button
          type="button"
          variant="secondary"
          disabled={currentPage === 0}
          onClick={() => setPage((value) => Math.max(0, value - 1))}
        >
          Previous
        </Button>
        <span className="text-sm text-slate-500">
          Page {currentPage + 1} of {pageCount}
        </span>
        <Button
          type="button"
          variant="secondary"
          disabled={currentPage >= pageCount - 1}
          onClick={() => setPage((value) => Math.min(pageCount - 1, value + 1))}
        >
          Next
        </Button>
      </div>
    </Card>
  );
}

function QueryResultDetail({ result }: { result: RagEvalQueryResultRead }) {
  const queryMetrics: Array<[string, unknown]> = [
    ["First relevant rank", result.first_relevant_rank],
    ["Hit at K", result.hit_at_k],
    ["MRR at K", result.mrr_at_k],
    ["Successful abstention", result.successful_abstention],
    ["False positive context", result.false_positive_context],
    ["Faithfulness", result.faithfulness],
    ["Answer relevancy", result.answer_relevancy],
    ["Context precision", result.context_precision],
    ["Context recall", result.context_recall],
    ["Answer correctness", result.answer_correctness],
  ];
  const chunks = [...(result.final_chunks ?? [])].sort((left, right) => left.rank - right.rank);

  return (
    <section
      role="region"
      aria-label={`Evidence for ${result.example_id}`}
      className="mt-4 grid gap-4 border-t border-slate-200 pt-4"
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h4 className="text-sm font-medium text-slate-950">Reference answer</h4>
          <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">
            {result.reference_answer ?? "Not available"}
          </p>
        </div>
        <div>
          <h4 className="text-sm font-medium text-slate-950">Actual answer</h4>
          <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">
            {result.actual_answer}
          </p>
        </div>
      </div>
      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {queryMetrics.map(([label, value]) => (
          <div key={label} className="rounded-xl bg-slate-50 px-3 py-2">
            <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
            <dd className="mt-1 text-sm text-slate-900">{formatScalar(value)}</dd>
          </div>
        ))}
      </dl>
      <div>
        <h4 className="text-sm font-medium text-slate-950">Final chunks</h4>
        <div className="mt-2 grid gap-3">
          {chunks.length ? (
            chunks.map((chunk) => {
              const metadata = chunk.metadata ?? {};
              const rawMetadataEntries: Array<[string, unknown]> = [
                ["Source", metadata.source],
                ["Score", metadata.score],
                ["Rerank score", metadata.rerank_score],
                ["Retrieval strategy", metadata.retrieval_strategy],
                ["Retrieval mode", metadata.retrieval_mode],
                ["Evidence path", metadata.evidence_path],
                ["Chunk index", metadata.chunk_index],
              ];
              const metadataEntries = rawMetadataEntries.filter(
                ([, value]) => value !== null && value !== undefined,
              );
              return (
                <article key={`${chunk.rank}-${chunk.content}`} className="rounded-xl bg-slate-50 p-3">
                  <h5 className="text-sm font-medium text-slate-950">Rank {chunk.rank}</h5>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{chunk.content}</p>
                  {metadataEntries.length ? (
                    <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                      {metadataEntries.map(([label, value]) => (
                        <div key={label}>
                          <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
                          <dd className="mt-0.5 break-words text-sm text-slate-900">
                            {formatScalar(value)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  ) : null}
                </article>
              );
            })
          ) : (
            <p className="text-sm text-slate-600">No final chunks were recorded.</p>
          )}
        </div>
      </div>
    </section>
  );
}

function MetricList({ metrics }: { metrics: Record<string, unknown> }) {
  const entries = metricEntries(metrics);
  return entries.length ? (
    <dl className="grid gap-2 sm:grid-cols-2">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-xl bg-slate-50 px-3 py-2">
          <dt className="text-xs uppercase tracking-wide text-slate-500">
            {humanizeMetric(key)}
          </dt>
          <dd className="mt-1 text-sm text-slate-900">{formatScalar(value)}</dd>
        </div>
      ))}
    </dl>
  ) : (
    <p className="text-sm text-slate-600">No metrics are available.</p>
  );
}

function humanizeMetric(key: string) {
  return key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function metricEntries(metrics: Record<string, unknown>) {
  return Object.entries(metrics).sort(([left], [right]) => left.localeCompare(right));
}

function formatScalar(value: unknown) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toFixed(3) : "—";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  if (typeof value === "string") {
    return value;
  }
  if (value === null || value === undefined) {
    return "—";
  }
  return JSON.stringify(value);
}

function formatProgress(value: number) {
  return Number.isFinite(value) ? Math.round(value) : 0;
}

function flattenSnapshot(
  value: Record<string, unknown>,
  prefix = "",
): Array<[string, unknown]> {
  return metricEntries(value).flatMap(([key, child]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return isRecord(child) ? flattenSnapshot(child, path) : [[path, child]];
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
