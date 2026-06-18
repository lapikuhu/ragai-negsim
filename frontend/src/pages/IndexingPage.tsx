import { useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { getErrorMessage } from "@/api/client";
import { formatDateTime } from "@/utils/format";
import {
  useChunkingProfilesQuery,
  useCorpusIndicesQuery,
  useEmbeddingModelsQuery,
  useVectorStoresQuery
} from "@/features/corpusIndices/corpusIndexQueries";
import { useCorporaQuery } from "@/features/corpora/corpusQueries";
import {
  useActiveIndexingJobQuery,
  useCancelIndexingJobMutation,
  useCreateIndexingJobMutation,
  useIndexingJobDetailQuery,
  useIndexingJobsQuery
} from "@/features/indexing/indexingQueries";

function formatElapsed(queuedAt?: string, completedAt?: string | null) {
  if (!queuedAt) {
    return "Not started";
  }
  const start = new Date(queuedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const totalSeconds = Math.max(0, Math.round((end - start) / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${seconds}s`;
}

export function IndexingPage() {
  const corpora = useCorporaQuery();
  const profiles = useChunkingProfilesQuery();
  const vectorStores = useVectorStoresQuery();
  const models = useEmbeddingModelsQuery();
  const indices = useCorpusIndicesQuery();
  const activeJob = useActiveIndexingJobQuery();
  const hasActiveJob = activeJob.data?.status === "queued" || activeJob.data?.status === "running";
  const jobs = useIndexingJobsQuery(hasActiveJob);
  const createMutation = useCreateIndexingJobMutation();
  const cancelMutation = useCancelIndexingJobMutation();

  const [corpusId, setCorpusId] = useState("");
  const [profileId, setProfileId] = useState("");
  const [vectorStoreId, setVectorStoreId] = useState("");
  const [modelName, setModelName] = useState("");
  const [indexName, setIndexName] = useState("");
  const [vectorNamespace, setVectorNamespace] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);

  const selectedDetailId = activeJob.data?.id ?? selectedJobId ?? null;
  const jobDetail = useIndexingJobDetailQuery(selectedDetailId);

  useEffect(() => {
    if (activeJob.data?.id) {
      setSelectedJobId((current) => current ?? activeJob.data?.id ?? null);
    }
  }, [activeJob.data?.id]);

  const availableProfiles = useMemo(() => profiles.data ?? [], [profiles.data]);
  const selectedModel = useMemo(
    () => (models.data ?? []).find((model) => model.name === modelName) ?? null,
    [modelName, models.data]
  );
  const selectedVectorStore = useMemo(
    () => (vectorStores.data ?? []).find((store) => store.id === Number(vectorStoreId || "0")) ?? null,
    [vectorStoreId, vectorStores.data]
  );
  const selectedCorpusIndices = useMemo(
    () => (indices.data ?? []).filter((index) => index.corpus_id === Number(corpusId || "0")),
    [corpusId, indices.data]
  );
  const dimensionWarning = getDimensionWarning(selectedModel, selectedVectorStore);
  const formDisabled = Boolean(activeJob.data) || createMutation.isPending || cancelMutation.isPending;

  if (
    corpora.isLoading ||
    profiles.isLoading ||
    vectorStores.isLoading ||
    models.isLoading ||
    jobs.isLoading ||
    indices.isLoading
  ) {
    return <LoadingState label="Loading indexing management..." />;
  }

  if (
    corpora.isError ||
    profiles.isError ||
    vectorStores.isError ||
    models.isError ||
    jobs.isError ||
    indices.isError
  ) {
    return (
      <ErrorState
        message={
          corpora.error?.message ??
          profiles.error?.message ??
          vectorStores.error?.message ??
          models.error?.message ??
          jobs.error?.message ??
          indices.error?.message ??
          "Unable to load indexing management."
        }
        onRetry={() => {
          void corpora.refetch();
          void profiles.refetch();
          void vectorStores.refetch();
          void models.refetch();
          void jobs.refetch();
          void indices.refetch();
        }}
      />
    );
  }

  const detail = activeJob.data ?? jobDetail.data ?? null;
  const warnings = detail?.warnings ?? [];
  const cancelRequested = detail ? getCancelRequested(detail) : false;
  const canCancel = Boolean(detail) && (detail?.status === "queued" || detail?.status === "running") && !cancelRequested;
  const progress = detail ? getProgressSnapshot(detail) : null;
  const currentActivity = detail ? getCurrentActivityMessage(detail) : null;

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Indexing"
        description="Run the full PDF-to-index pipeline for a corpus and monitor the resulting background job from one place."
      />

      <Card className="border-amber-200 bg-amber-50/80">
        <h2 className="text-lg font-semibold text-amber-950">Important</h2>
        <p className="mt-2 text-sm text-amber-900">
          Only one indexing job can run at a time. Do not shut down or restart the app while a job is queued or running,
          because FastAPI background tasks do not survive application shutdown.
        </p>
        <p className="mt-2 text-sm text-amber-900">
          Cancelling an indexing job stops future work and leaves any partial build artifacts in place, but cancelled candidate
          indexes are not activated for normal use.
        </p>
        <p className="mt-2 text-sm text-amber-900">
          A 100 page pdf takes about 4 to 5 minutes to index for a default recursive chunking profile with a small 
          384-dimensional embedding model on a respectable 2024 laptop. Your mileage may vary. Be patient!
        </p>
      </Card>

      <Card>
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Queue indexing job</h2>
            <p className="mt-1 text-sm text-slate-600">
              Select a corpus, chunking profile, embedding model, vector store, and the human-readable name for the resulting index.
            </p>
          </div>
          {activeJob.data ? <StatusBadge status={activeJob.data.status} /> : null}
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Field label="Corpus">
            <Select value={corpusId} onChange={(event) => setCorpusId(event.target.value)} disabled={formDisabled}>
              <option value="">Select corpus</option>
              {(corpora.data ?? []).map((corpus) => (
                <option key={corpus.id} value={corpus.id}>
                  {corpus.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Chunking profile" hint="Semantic and hybrid profiles use the selected embedding model during chunking before final indexing.">
            <Select value={profileId} onChange={(event) => setProfileId(event.target.value)} disabled={formDisabled}>
              <option value="">Select profile</option>
              {availableProfiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Embedding model" hint={selectedModel ? `Dimensions: ${selectedModel.dimensionality}` : undefined}>
            <Select value={modelName} onChange={(event) => setModelName(event.target.value)} disabled={formDisabled}>
              <option value="">Select model</option>
              {(models.data ?? []).map((model) => (
                <option key={model.name} value={model.name}>
                  {model.display_name}
                </option>
              ))}
            </Select>
          </Field>
          <Field
            label="Vector store"
            hint={selectedVectorStore ? formatVectorStoreDimensions(selectedVectorStore.embedding_dimensions) : undefined}
          >
            <Select value={vectorStoreId} onChange={(event) => setVectorStoreId(event.target.value)} disabled={formDisabled}>
              <option value="">Select vector store</option>
              {(vectorStores.data ?? []).map((store) => (
                <option key={store.id} value={store.id}>
                  {store.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Index name" hint="This must be unique. Use a different name to create another index for the same corpus.">
            <Input value={indexName} onChange={(event) => setIndexName(event.target.value)} disabled={formDisabled} />
          </Field>
          <Field label="Vector namespace" hint="Optional. Leave blank to let the backend generate a namespace automatically.">
            <Input
              value={vectorNamespace}
              onChange={(event) => setVectorNamespace(event.target.value)}
              disabled={formDisabled}
              placeholder="Optional namespace"
            />
          </Field>
        </div>
        {selectedCorpusIndices.length ? (
          <div className="mt-4 rounded-xl bg-slate-50 p-4">
            <h3 className="text-sm font-semibold text-slate-900">Existing indices for the selected corpus</h3>
            <div className="mt-3 grid gap-2">
              {selectedCorpusIndices.map((index) => (
                <div key={index.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2">
                  <div>
                    <p className="text-sm font-medium text-slate-900">{index.name}</p>
                    <p className="text-xs text-slate-500">
                      Profile #{index.chunking_profile_id} · Store #{index.vector_store_id} · {index.embedding_model}
                    </p>
                  </div>
                  <StatusBadge status={index.status} />
                </div>
              ))}
            </div>
          </div>
        ) : null}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button
            type="button"
            disabled={!corpusId || !profileId || !vectorStoreId || !modelName || !indexName || Boolean(dimensionWarning) || formDisabled}
            onClick={async () => {
              try {
                const queued = await createMutation.mutateAsync({
                  corpus_id: Number(corpusId),
                  chunking_profile_id: Number(profileId),
                  vector_store_id: Number(vectorStoreId),
                  embedding_model: modelName,
                  requested_index_name: indexName,
                  requested_vector_namespace: vectorNamespace.trim() || null,
                  status: "queued",
                  stage: "validating"
                });
                setMessage(`Queued indexing job #${queued.id}. Keep this application running until the job finishes.`);
                setSelectedJobId(queued.id);
              } catch (error) {
                setMessage(getErrorMessage(error));
              }
            }}
          >
            {createMutation.isPending ? "Queueing..." : "Index corpus"}
          </Button>
          {dimensionWarning ? <p className="text-sm font-medium text-amber-800">{dimensionWarning}</p> : null}
          {message ? <p className="text-sm text-slate-600">{message}</p> : null}
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)]">
        <Card>
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-950">Current or selected job</h2>
            {canCancel && detail ? (
              <Button
                type="button"
                variant="danger"
                disabled={cancelMutation.isPending}
                onClick={async () => {
                  try {
                    const cancelled = await cancelMutation.mutateAsync(detail.id);
                    if (cancelled.status === "cancelled") {
                      setMessage(`Cancelled indexing job #${detail.id}. You can queue a new job now.`);
                    } else {
                      setMessage(`Cancellation requested for indexing job #${detail.id}. The current step will finish before the job stops.`);
                    }
                  } catch (error) {
                    setMessage(getErrorMessage(error));
                  }
                }}
              >
                {cancelMutation.isPending ? "Cancelling..." : "Cancel indexing job"}
              </Button>
            ) : null}
          </div>
          {detail ? (
            <div className="mt-4 grid gap-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">{detail.requested_index_name}</p>
                  <p className="text-xs text-slate-500">Job #{detail.id}</p>
                </div>
                <StatusBadge status={detail.status} />
              </div>
              {cancelRequested && detail.status === "running" ? (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                  Cancelling after the current step finishes.
                </div>
              ) : null}
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-xl bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Stage</p>
                  <p className="mt-2 text-lg font-semibold capitalize text-slate-950">{formatStageLabel(detail.stage)}</p>
                </div>
                <div className="rounded-xl bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Elapsed</p>
                  <p className="mt-2 text-lg font-semibold text-slate-950">
                    {formatElapsed(detail.queued_at, detail.completed_at ?? null)}
                  </p>
                </div>
                <div className="rounded-xl bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Documents</p>
                  <p className="mt-2 text-lg font-semibold text-slate-950">
                    {detail.processed_documents} / {detail.total_documents}
                  </p>
                </div>
                <div className="rounded-xl bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Chunks</p>
                  <p className="mt-2 text-lg font-semibold text-slate-950">
                    {detail.chunks_indexed || detail.chunks_created}
                  </p>
                </div>
              </div>
              {progress ? (
                <div className="rounded-xl border border-slate-200 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-slate-900">{progress.label}</p>
                    <p className="text-xs text-slate-500">
                      {progress.current} / {progress.total}
                    </p>
                  </div>
                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
                    <div
                      className="h-full rounded-full bg-slate-900 transition-[width] duration-300"
                      style={{ width: `${Math.max(6, progress.percent)}%` }}
                    />
                  </div>
                </div>
              ) : null}
              <div className="rounded-xl border border-slate-200 p-4">
                <p className="text-sm font-medium text-slate-900">Current activity</p>
                <p className="mt-2 text-sm text-slate-600">{currentActivity}</p>
              </div>
              {detail.failure_detail ? (
                <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{detail.failure_detail}</div>
              ) : null}
              <div className="rounded-xl border border-slate-200 p-4">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-semibold text-slate-900">Warnings</h3>
                  <span className="text-xs text-slate-500">{warnings.length}</span>
                </div>
                {warnings.length ? (
                  <div className="mt-3 grid gap-2">
                    {warnings.map((warning, index) => (
                      <div key={`${warning.document_name ?? "warning"}-${index}`} className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
                        <p className="font-medium">{warning.document_name ?? "Document warning"}</p>
                        <p className="mt-1">{warning.message}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-slate-600">No warnings recorded for this job.</p>
                )}
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-600">No indexing job is selected. Queue a job or pick one from the history panel.</p>
          )}
        </Card>

        <Card>
          <h2 className="text-lg font-semibold text-slate-950">Job history</h2>
          <div className="mt-4 grid gap-3">
            {(jobs.data ?? []).length ? (
              jobs.data?.map((job) => (
                <button
                  key={job.id}
                  type="button"
                  className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-left transition hover:border-slate-300 hover:bg-slate-50"
                  onClick={() => setSelectedJobId(job.id)}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-slate-900">{job.requested_index_name}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        Corpus #{job.corpus_id} · queued {formatDateTime(job.queued_at)}
                      </p>
                    </div>
                    <StatusBadge status={job.status} />
                  </div>
                </button>
              ))
            ) : (
              <p className="text-sm text-slate-600">No indexing jobs have been recorded yet.</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function formatVectorStoreDimensions(dimensions?: number | null) {
  return dimensions ? `Dimensions: ${dimensions}` : "Dimensions not set";
}

function getDimensionWarning(
  selectedModel: { dimensionality: number } | null,
  selectedVectorStore: { embedding_dimensions?: number | null } | null,
) {
  if (!selectedModel || !selectedVectorStore) {
    return null;
  }
  if (!selectedVectorStore.embedding_dimensions) {
    return "The selected vector store does not have dimensions set and cannot be used for indexing.";
  }
  if (selectedModel.dimensionality !== selectedVectorStore.embedding_dimensions) {
    return `Embedding model dimensions (${selectedModel.dimensionality}) do not match vector store dimensions (${selectedVectorStore.embedding_dimensions}).`;
  }
  return null;
}

function formatStageLabel(stage: string) {
  switch (stage) {
    case "converting":
      return "Converting to markdown";
    case "cleaning":
      return "Cleaning markdown";
    case "chunking":
      return "Chunking document";
    case "embedding":
      return "Embedding chunks";
    case "finalizing":
      return "Finalizing index";
    default:
      return stage.replaceAll("_", " ");
  }
}

function getCurrentActivityMessage(detail: {
  status: string;
  stage: string;
  current_document_name?: string | null;
}) {
  if (getCancelRequested(detail) && detail.status === "running") {
    return "Cancellation requested. The current step will finish before the job stops.";
  }
  if (detail.stage === "embedding") {
    return "All documents ingested. Embedding chunks now.";
  }
  if (detail.stage === "finalizing") {
    return "Activating the candidate index.";
  }
  if (detail.current_document_name) {
    return detail.current_document_name;
  }
  return "Waiting for the next indexing step to start.";
}

function getCancelRequested(detail: object) {
  return Boolean((detail as { cancel_requested?: boolean }).cancel_requested);
}

function getProgressSnapshot(detail: {
  stage: string;
  total_documents: number;
  processed_documents: number;
  chunks_created: number;
  chunks_indexed: number;
}) {
  if (detail.stage === "embedding" && detail.chunks_created > 0) {
    return buildProgressSnapshot("Chunks indexed", detail.chunks_indexed, detail.chunks_created);
  }
  if (detail.total_documents > 0) {
    return buildProgressSnapshot("Documents ingested", detail.processed_documents, detail.total_documents);
  }
  return null;
}

function buildProgressSnapshot(label: string, current: number, total: number) {
  const clampedCurrent = Math.min(Math.max(current, 0), total);
  const percent = total > 0 ? Math.round((clampedCurrent / total) * 100) : 0;
  return {
    label,
    current: clampedCurrent,
    total,
    percent,
  };
}
