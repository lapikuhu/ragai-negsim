import { useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";

import { getErrorMessage } from "@/api/client";
import { DataTable } from "@/components/common/DataTable";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { RagEvaluationForm } from "@/features/ragEvaluation/RagEvaluationForm";
import { RagEvaluationHistory } from "@/features/ragEvaluation/RagEvaluationHistory";
import {
  useCancelRagEvalRunMutation,
  useCreateRagEvalConfigurationMutation,
  useDeleteRagEvalConfigurationMutation,
  useEnqueueRagEvalRunMutation,
  useLatestRagEvalRuns,
  useRagEvalConfigurationsQuery,
  useUpdateRagEvalConfigurationMutation,
} from "@/features/ragEvaluation/ragEvaluationQueries";
import {
  makeCragConfiguration,
  type RagEvalConfigurationInput,
  type RagEvalConfigurationRead,
  type RagEvalRunRead,
} from "@/features/ragEvaluation/ragEvaluationTypes";
import { formatDateTime, toSentenceCase } from "@/utils/format";

const configurationLimit = 20;
const cleanupBlockedMessage =
  "Queue execution is blocked. Graph cleanup must succeed before later experiments can start. The coordinator will retry automatically; check Neo4j connectivity if this state persists.";

type EditorState =
  | { mode: "create"; initialValue: RagEvalConfigurationInput }
  | { mode: "edit"; configuration: RagEvalConfigurationRead };

type SelectedHistoryConfiguration = {
  id: number;
  name: string;
};

export function RagEvaluationsPage() {
  const [configurationSkip, setConfigurationSkip] = useState(0);
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [selectedHistoryConfiguration, setSelectedHistoryConfiguration] =
    useState<SelectedHistoryConfiguration | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [editorError, setEditorError] = useState<string | null>(null);

  const configurationsQuery = useRagEvalConfigurationsQuery(
    configurationSkip,
    configurationLimit,
  );
  const configurations = configurationsQuery.data ?? [];
  const latestRunQueries = useLatestRagEvalRuns(
    useMemo(() => configurations.map((configuration) => configuration.id), [configurations]),
  );
  const createMutation = useCreateRagEvalConfigurationMutation();
  const updateMutation = useUpdateRagEvalConfigurationMutation();
  const deleteMutation = useDeleteRagEvalConfigurationMutation();
  const enqueueMutation = useEnqueueRagEvalRunMutation();
  const cancelMutation = useCancelRagEvalRunMutation();

  const latestRuns = configurations.map(
    (_configuration, index) => latestRunQueries[index]?.data ?? null,
  );
  const cleanupBlocked = latestRuns.some(
    (run) => run?.status === "running" && run.stage === "cleanup_pending",
  );

  function openCreateForm() {
    const initialValue = makeCragConfiguration();
    initialValue.name = "";
    setMessage(null);
    setEditorError(null);
    setEditor({ mode: "create", initialValue });
  }

  async function deleteConfiguration(configuration: RagEvalConfigurationRead) {
    if (
      !window.confirm(
        `Delete RAG evaluation configuration "${configuration.name}"?`,
      )
    ) {
      return;
    }
    setMessage(null);
    try {
      await deleteMutation.mutateAsync(configuration.id);
      if (selectedHistoryConfiguration?.id === configuration.id) {
        setSelectedHistoryConfiguration(null);
      }
      setMessage(`Deleted ${configuration.name}.`);
    } catch (error) {
      setMessage(getErrorMessage(error, "Unable to delete RAG evaluation configuration."));
    }
  }

  async function enqueueRun(configuration: RagEvalConfigurationRead) {
    setMessage(null);
    try {
      await enqueueMutation.mutateAsync(configuration.id);
      setMessage(`Queued ${configuration.name}.`);
    } catch (error) {
      setMessage(getErrorMessage(error, "Unable to enqueue RAG evaluation run."));
    }
  }

  async function cancelRun(run: RagEvalRunRead) {
    setMessage(null);
    try {
      await cancelMutation.mutateAsync(run.id);
      setMessage(`Cancellation requested for run ${run.id}.`);
    } catch (error) {
      setMessage(getErrorMessage(error, "Unable to cancel RAG evaluation run."));
    }
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        title="RAG Evaluation"
        description="Configure, run, and compare isolated production RAG experiments."
        actions={(
          <Button type="button" onClick={openCreateForm}>
            Create experiment
          </Button>
        )}
      />

      {cleanupBlocked ? (
        <div
          role="alert"
          className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950"
        >
          {cleanupBlockedMessage}
        </div>
      ) : null}

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Experiments</h2>
            <p className="mt-1 text-sm text-slate-600">
              Each row shows the latest run for that saved configuration.
            </p>
          </div>
          {message ? (
            <p role="status" className="text-sm text-slate-700">
              {message}
            </p>
          ) : null}
        </div>

        <div className="mt-4">
          {configurationsQuery.isLoading ? (
            <LoadingState label="Loading RAG evaluation configurations..." />
          ) : configurationsQuery.isError ? (
            <ErrorState
              message={getErrorMessage(
                configurationsQuery.error,
                "Unable to load RAG evaluation configurations.",
              )}
              onRetry={() => configurationsQuery.refetch()}
            />
          ) : configurations.length ? (
            <DataTable
              rows={configurations}
              columns={[
                {
                  key: "configuration",
                  header: "Configuration",
                  render: (configuration) => (
                    <div>
                      <div className="font-medium text-slate-950">{configuration.name}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        Updated {formatDateTime(configuration.last_updated)}
                      </div>
                    </div>
                  ),
                },
                {
                  key: "chunking",
                  header: "Chunking",
                  render: (configuration) => summarizeChunking(configuration),
                },
                {
                  key: "rag",
                  header: "RAG strategy",
                  render: (configuration) => summarizeRag(configuration),
                },
                {
                  key: "latest",
                  header: "Latest status",
                  render: (configuration) => {
                    const index = configurations.findIndex((item) => item.id === configuration.id);
                    const query = latestRunQueries[index];
                    const run = query?.data;
                    if (query?.isLoading) {
                      return <span className="text-xs text-slate-500">Loading latest run...</span>;
                    }
                    if (query?.isError) {
                      return (
                        <span className="text-xs text-red-700">
                          {getErrorMessage(query.error, "Latest run unavailable.")}
                        </span>
                      );
                    }
                    if (!run) {
                      return <span className="text-sm text-slate-500">Never run</span>;
                    }
                    return (
                      <div className="grid gap-1">
                        <div><StatusBadge status={run.status} /></div>
                        <div className="text-xs capitalize text-slate-600">
                          {toSentenceCase(run.stage)} · {Math.round(run.progress)}%
                        </div>
                        <div className="text-xs text-slate-500">
                          {run.completed_examples}/{run.total_examples} examples
                        </div>
                      </div>
                    );
                  },
                },
                {
                  key: "overall-score",
                  header: "Overall score",
                  render: (configuration) =>
                    formatMetric(latestRunFor(configuration.id, configurations, latestRunQueries), "overall_score"),
                },
                {
                  key: "hit-at-k",
                  header: "Hit@K",
                  render: (configuration) =>
                    formatMetric(latestRunFor(configuration.id, configurations, latestRunQueries), "hit_at_k"),
                },
                {
                  key: "mrr-at-k",
                  header: "MRR@K",
                  render: (configuration) =>
                    formatMetric(latestRunFor(configuration.id, configurations, latestRunQueries), "mrr_at_k"),
                },
                {
                  key: "actions",
                  header: "Actions",
                  render: (configuration) => {
                    const run = latestRunFor(configuration.id, configurations, latestRunQueries);
                    const active = run?.status === "queued" || run?.status === "running";
                    return (
                      <div className="flex min-w-72 flex-wrap gap-2">
                        <Button
                          type="button"
                          aria-label={`Run ${configuration.name}`}
                          disabled={active || enqueueMutation.isPending}
                          onClick={() => void enqueueRun(configuration)}
                        >
                          Run
                        </Button>
                        {active && run ? (
                          <Button
                            type="button"
                            variant="secondary"
                            aria-label={`Cancel ${configuration.name}`}
                            disabled={run.cancel_requested || cancelMutation.isPending}
                            onClick={() => void cancelRun(run)}
                          >
                            {run.cancel_requested ? "Cancelling..." : "Cancel"}
                          </Button>
                        ) : null}
                        <Button
                          type="button"
                          variant="secondary"
                          aria-label={`History for ${configuration.name}`}
                          onClick={() =>
                            setSelectedHistoryConfiguration({
                              id: configuration.id,
                              name: configuration.name,
                            })
                          }
                        >
                          History
                        </Button>
                        {run ? (
                          <Link
                            className="inline-flex items-center justify-center rounded-lg px-3 py-2 text-sm font-medium text-accent hover:bg-teal-50"
                            aria-label={`View result for ${configuration.name}`}
                            to={`/rag-evaluations/runs/${run.id}`}
                          >
                            View result
                          </Link>
                        ) : null}
                        <Button
                          type="button"
                          variant="ghost"
                          aria-label={`Edit ${configuration.name}`}
                          onClick={() => {
                            setMessage(null);
                            setEditorError(null);
                            setEditor({ mode: "edit", configuration });
                          }}
                        >
                          Edit
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          aria-label={`Delete ${configuration.name}`}
                          disabled={deleteMutation.isPending}
                          onClick={() => void deleteConfiguration(configuration)}
                        >
                          Delete
                        </Button>
                      </div>
                    );
                  },
                },
              ]}
            />
          ) : (
            <EmptyState
              title="No RAG evaluation configurations"
              description="Create an experiment to start evaluating the production RAG pipeline."
              action={<Button onClick={openCreateForm}>Create experiment</Button>}
            />
          )}
        </div>

        {!configurationsQuery.isLoading && !configurationsQuery.isError ? (
          <div className="mt-4 flex items-center justify-between gap-3">
            <Button
              type="button"
              variant="secondary"
              disabled={configurationSkip === 0}
              onClick={() =>
                setConfigurationSkip((current) => Math.max(0, current - configurationLimit))
              }
            >
              Previous configurations
            </Button>
            <span className="text-sm text-slate-500">
              {configurations.length === 0
                ? "0 configurations"
                : `Configurations ${configurationSkip + 1}–${configurationSkip + configurations.length}`}
            </span>
            <Button
              type="button"
              variant="secondary"
              disabled={configurations.length < configurationLimit}
              onClick={() => setConfigurationSkip((current) => current + configurationLimit)}
            >
              Next configurations
            </Button>
          </div>
        ) : null}
      </Card>

      {selectedHistoryConfiguration ? (
        <RagEvaluationHistory
          key={selectedHistoryConfiguration.id}
          configurationId={selectedHistoryConfiguration.id}
          configurationName={selectedHistoryConfiguration.name}
          onClose={() => setSelectedHistoryConfiguration(null)}
        />
      ) : null}

      {editor ? (
        <ConfigurationEditor
          key={editor.mode === "create" ? "create" : `edit-${editor.configuration.id}`}
          editor={editor}
          createPending={createMutation.isPending}
          updatePending={updateMutation.isPending}
          error={editorError}
          onCancel={() => {
            setEditor(null);
            setEditorError(null);
          }}
          onCreate={async (input) => {
            setMessage(null);
            setEditorError(null);
            try {
              await createMutation.mutateAsync(input);
              setEditor(null);
              setMessage(`Created ${input.name}.`);
            } catch (error) {
              setEditorError(
                `${getErrorMessage(error, "Unable to create RAG evaluation configuration.")} Review the configuration and try again.`,
              );
            }
          }}
          onUpdate={async (configuration, input) => {
            setMessage(null);
            setEditorError(null);
            try {
              await updateMutation.mutateAsync({ id: configuration.id, input });
              setEditor(null);
              setMessage(`Updated ${input.name}.`);
            } catch (error) {
              setEditorError(
                `${getErrorMessage(error, "Unable to update RAG evaluation configuration.")} Review the configuration and try again.`,
              );
            }
          }}
        />
      ) : null}
    </div>
  );
}

function ConfigurationEditor({
  editor,
  createPending,
  updatePending,
  error,
  onCancel,
  onCreate,
  onUpdate,
}: {
  editor: EditorState;
  createPending: boolean;
  updatePending: boolean;
  error: string | null;
  onCancel: () => void;
  onCreate: (input: RagEvalConfigurationInput) => Promise<void>;
  onUpdate: (
    configuration: RagEvalConfigurationRead,
    input: RagEvalConfigurationInput,
  ) => Promise<void>;
}) {
  const creating = editor.mode === "create";
  const title = creating ? "Create experiment" : `Edit ${editor.configuration.name}`;
  const initialValue = creating
    ? editor.initialValue
    : configurationToInput(editor.configuration);
  const pending = createPending || updatePending;
  const overlayRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const pendingRef = useRef(pending);
  const submissionInFlightRef = useRef(false);
  const onCancelRef = useRef(onCancel);
  const titleId = useId();
  const descriptionId = useId();
  pendingRef.current = pending;
  onCancelRef.current = onCancel;

  function requestClose() {
    if (!pendingRef.current && !submissionInFlightRef.current) {
      onCancelRef.current();
    }
  }

  useLayoutEffect(() => {
    const overlay = overlayRef.current;
    const dialog = dialogRef.current;
    if (!overlay || !dialog) {
      return;
    }
    const dialogElement = dialog;

    const opener = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const previousOverflow = document.body.style.overflow;
    const siblings = Array.from(document.body.children).filter(
      (element): element is HTMLElement => element instanceof HTMLElement && element !== overlay,
    );
    const siblingStates = siblings.map((element) => ({
      element,
      hadInert: element.hasAttribute("inert"),
      ariaHidden: element.getAttribute("aria-hidden"),
    }));

    document.body.style.overflow = "hidden";
    for (const sibling of siblings) {
      sibling.setAttribute("inert", "");
      sibling.setAttribute("aria-hidden", "true");
    }
    (focusableElements(dialogElement)[0] ?? dialogElement).focus();

    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        if (!pendingRef.current && !submissionInFlightRef.current) {
          event.preventDefault();
          onCancelRef.current();
        }
        return;
      }
      if (event.key !== "Tab") {
        return;
      }

      const focusable = focusableElements(dialogElement);
      if (focusable.length === 0) {
        event.preventDefault();
        dialogElement.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (
        event.shiftKey &&
        (document.activeElement === first || !dialogElement.contains(document.activeElement))
      ) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      for (const { element, hadInert, ariaHidden } of siblingStates) {
        if (!hadInert) {
          element.removeAttribute("inert");
        }
        if (ariaHidden === null) {
          element.removeAttribute("aria-hidden");
        } else {
          element.setAttribute("aria-hidden", ariaHidden);
        }
      }
      opener?.focus();
    };
  }, []);

  return createPortal(
    <div
      ref={overlayRef}
      className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/45 p-4"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
        className="max-h-[90vh] w-full max-w-5xl overflow-y-auto"
      >
        <Card>
          <div className="mb-5">
            <h2 id={titleId} className="text-xl font-semibold text-slate-950">{title}</h2>
            <p id={descriptionId} className="mt-1 text-sm text-slate-600">
              Define the chunking, retrieval, and metric settings for this experiment.
            </p>
          </div>
          {error ? (
            <p
              role="alert"
              className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
            >
              {error}
            </p>
          ) : null}
          <RagEvaluationForm
            initialValue={initialValue}
            submitLabel={creating ? "Create experiment" : "Save experiment"}
            onCancel={requestClose}
            onSubmissionStateChange={(inFlight) => {
              submissionInFlightRef.current = inFlight;
            }}
            pending={pending}
            onSubmit={(input) =>
              creating
                ? onCreate(input)
                : onUpdate(editor.configuration, input)
            }
          />
          {pending ? (
            <p className="mt-3 text-sm text-slate-500">Saving experiment...</p>
          ) : null}
        </Card>
      </div>
    </div>,
    document.body,
  );
}

function focusableElements(container: HTMLElement) {
  return Array.from(
    container.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((element) => !element.hidden && element.getAttribute("aria-hidden") !== "true");
}

function configurationToInput(
  configuration: RagEvalConfigurationRead,
): RagEvalConfigurationInput {
  return {
    name: configuration.name,
    chunking: structuredClone(configuration.chunking),
    rag: structuredClone(configuration.rag),
    metrics: structuredClone(configuration.metrics),
  };
}

function latestRunFor(
  configurationId: number,
  configurations: RagEvalConfigurationRead[],
  latestRunQueries: ReturnType<typeof useLatestRagEvalRuns>,
) {
  const index = configurations.findIndex((configuration) => configuration.id === configurationId);
  return latestRunQueries[index]?.data ?? null;
}

function summarizeChunking(configuration: RagEvalConfigurationRead) {
  const chunking = configuration.chunking;
  if (chunking.strategy === "recursive") {
    return `Recursive · ${chunking.chunk_size} size · ${chunking.chunk_overlap} overlap`;
  }
  if (chunking.strategy === "semantic") {
    return `Semantic · ${chunking.breakpoint_threshold_type} ${chunking.breakpoint_threshold_amount}`;
  }
  return `Hybrid · ${chunking.chunk_size} size · ${chunking.breakpoint_threshold_type} ${chunking.breakpoint_threshold_amount}`;
}

function summarizeRag(configuration: RagEvalConfigurationRead) {
  const rag = configuration.rag;
  if (rag.strategy === "crag") {
    return `CRAG · top ${rag.top_k} · ${toSentenceCase(rag.reranker)}`;
  }
  return `GraphRAG · ${toSentenceCase(rag.retrieval_mode)} · depth ${rag.traversal_depth}`;
}

function formatMetric(run: RagEvalRunRead | null, key: string) {
  const value = run?.overall_metrics[key];
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "—";
}
