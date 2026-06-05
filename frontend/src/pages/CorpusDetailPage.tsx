import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  useCreateCorpusMutation,
  useChunkCorpusMutation,
  useCorporaQuery,
  useIngestCorpusMutation,
  useQueueEmbedJobMutation
} from "@/features/corpora/corpusQueries";
import {
  useChunkingProfilesQuery,
  useCorpusIndicesQuery,
  useEmbeddingModelsQuery,
  useVectorStoresQuery
} from "@/features/corpusIndices/corpusIndexQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { KeyValueList } from "@/components/common/KeyValueList";
import { StatusBadge } from "@/components/common/StatusBadge";
import { QueuedJobNotice } from "@/features/ingestion/ingestionComponents";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/api/client";

export function CorpusDetailPage() {
  const corpusId = Number(useParams().corpusId);
  const corpora = useCorporaQuery();
  const indices = useCorpusIndicesQuery();
  const profiles = useChunkingProfilesQuery();
  const vectorStores = useVectorStoresQuery();
  const models = useEmbeddingModelsQuery();
  const ingestMutation = useIngestCorpusMutation(corpusId);
  const chunkMutation = useChunkCorpusMutation(corpusId);
  const [profileId, setProfileId] = useState("");
  const [vectorStoreId, setVectorStoreId] = useState("");
  const [modelName, setModelName] = useState("");
  const [embedName, setEmbedName] = useState("");
  const [queueNotice, setQueueNotice] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const corpus = useMemo(() => (corpora.data ?? []).find((item) => item.id === corpusId), [corpora.data, corpusId]);
  const relatedIndices = useMemo(
    () => (indices.data ?? []).filter((index) => index.corpus_id === corpusId),
    [corpusId, indices.data]
  );

  const queueMutation = useQueueEmbedJobMutation(corpusId, Number(profileId || "0"), Number(vectorStoreId || "0"));

  if (corpora.isLoading) {
    return <LoadingState label="Loading corpus..." />;
  }

  if (corpora.isError) {
    return <ErrorState message={corpora.error.message} onRetry={() => corpora.refetch()} />;
  }

  if (!corpus) {
    return (
      <ErrorState
        title="Corpus detail is partial"
        message="The backend does not expose `GET /corpora/{id}`. This screen resolves detail from the list endpoint and could not find the requested corpus."
      />
    );
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        title={corpus.name}
        description={corpus.description ?? "Corpus detail derived from list data because a dedicated corpus read endpoint is not exposed."}
      />

      <Card>
        <KeyValueList
          items={[
            { label: "Corpus ID", value: corpus.id },
            { label: "Created by", value: corpus.created_by_user_id },
            { label: "Last edited by", value: corpus.last_edit_by_user_id ?? "Not recorded" },
            { label: "Created at", value: formatDateTime(corpus.created_at) }
          ]}
        />
      </Card>

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Chunk and ingest</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,280px)_1fr]">
          <Field label="Chunking profile">
            <Select value={profileId} onChange={(event) => setProfileId(event.target.value)}>
              <option value="">Select profile</option>
              {(profiles.data ?? []).map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </Select>
          </Field>
          <div className="flex flex-wrap items-end gap-3">
            <Button
              type="button"
              variant="secondary"
              disabled={!profileId || ingestMutation.isPending}
              onClick={async () => {
                try {
                  await ingestMutation.mutateAsync(Number(profileId));
                  setMessage("Corpus ingest completed.");
                } catch (error) {
                  setMessage(getErrorMessage(error));
                }
              }}
            >
              Ingest corpus
            </Button>
            <Button
              type="button"
              disabled={!profileId || chunkMutation.isPending}
              onClick={async () => {
                try {
                  await chunkMutation.mutateAsync(Number(profileId));
                  setMessage("Corpus chunking completed.");
                } catch (error) {
                  setMessage(getErrorMessage(error));
                }
              }}
            >
              Chunk corpus
            </Button>
          </div>
        </div>
        {message ? <p className="mt-3 text-sm text-slate-600">{message}</p> : null}
      </Card>

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Queue embedding job</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Field label="Chunking profile">
            <Select value={profileId} onChange={(event) => setProfileId(event.target.value)}>
              <option value="">Select profile</option>
              {(profiles.data ?? []).map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Vector store">
            <Select value={vectorStoreId} onChange={(event) => setVectorStoreId(event.target.value)}>
              <option value="">Select vector store</option>
              {(vectorStores.data ?? []).map((store) => (
                <option key={store.id} value={store.id}>
                  {store.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Job name">
            <Input value={embedName} onChange={(event) => setEmbedName(event.target.value)} />
          </Field>
          <Field label="Embedding model">
            <Select value={modelName} onChange={(event) => setModelName(event.target.value)}>
              <option value="">Select model</option>
              {(models.data ?? []).map((model) => (
                <option key={model.name} value={model.name}>
                  {model.display_name}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="mt-4">
          <Button
            type="button"
            disabled={!profileId || !vectorStoreId || !modelName || !embedName || queueMutation.isPending}
            onClick={async () => {
              try {
                const queued = await queueMutation.mutateAsync({
                  name: embedName,
                  embedding_model: modelName,
                  vector_namespace: null
                });
                setQueueNotice(
                  `Queued corpus index #${queued.corpus_index_id}. The backend returns 202 Accepted, but there is no dedicated polling screen yet.`
                );
              } catch (error) {
                setQueueNotice(getErrorMessage(error));
              }
            }}
          >
            {queueMutation.isPending ? "Queueing..." : "Queue embed job"}
          </Button>
        </div>
      </Card>

      {queueNotice ? (
        <QueuedJobNotice
          title="Embedding job state"
          description={queueNotice}
          actionLabel="Dismiss"
          onAction={() => setQueueNotice(null)}
        />
      ) : null}

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Related corpus indices</h2>
        <div className="mt-4 grid gap-3">
          {relatedIndices.length ? (
            relatedIndices.map((index) => (
              <div key={index.id} className="rounded-xl bg-slate-50 p-3">
                <div className="flex items-center justify-between gap-3">
                  <strong>{index.name}</strong>
                  <StatusBadge status={index.status} />
                </div>
                <p className="mt-2 text-sm text-slate-600">
                  Model: {index.embedding_model} · Vector store #{index.vector_store_id} · Profile #{index.chunking_profile_id}
                </p>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-600">No indices linked to this corpus yet.</p>
          )}
        </div>
      </Card>
    </div>
  );
}
