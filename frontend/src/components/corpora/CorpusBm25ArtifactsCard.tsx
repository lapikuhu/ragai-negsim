import { useState } from "react";
import { Link } from "react-router-dom";

import { getErrorMessage } from "@/api/client";
import { ErrorState } from "@/components/common/ErrorState";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field, Input, Select } from "@/components/ui/Field";
import {
  useCancelCorpusBm25BuildJobMutation,
  useCorpusBm25BuildJobsQuery,
  useCorpusBm25NameAvailabilityQuery,
  useCorpusChunkSetsQuery,
  useQueueCorpusBm25BuildJobMutation,
  useRetryCorpusBm25BuildJobMutation,
} from "@/features/corpusBm25BuildJobs/corpusBm25BuildJobQueries";
import { useCorpusBm25IndicesQuery } from "@/features/corpusBm25Indices/corpusBm25IndexQueries";
import { formatDateTime } from "@/utils/format";

type Props = { corpusId: number; corpusName: string };

export function CorpusBm25ArtifactsCard({ corpusId, corpusName }: Props) {
  const artifacts = useCorpusBm25IndicesQuery(corpusId, { status: null });
  const chunkSets = useCorpusChunkSetsQuery(corpusId);
  const jobs = useCorpusBm25BuildJobsQuery(corpusId);
  const queue = useQueueCorpusBm25BuildJobMutation(corpusId);
  const cancel = useCancelCorpusBm25BuildJobMutation(corpusId);
  const retry = useRetryCorpusBm25BuildJobMutation(corpusId);
  const [open, setOpen] = useState(false);
  const [chunkSetId, setChunkSetId] = useState("");
  const [name, setName] = useState("");
  const [nameEdited, setNameEdited] = useState(false);
  const [retryJobId, setRetryJobId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const nameAvailability = useCorpusBm25NameAvailabilityQuery(name);

  const setsById = new Map((chunkSets.data ?? []).map((item) => [item.id, item]));

  function closeModal() {
    setOpen(false);
    setChunkSetId("");
    setName("");
    setNameEdited(false);
    setRetryJobId(null);
    setError(null);
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">BM25 artifacts</h2>
          <p className="mt-1 text-sm text-slate-600">Lexical retrieval artifacts built from a named persisted chunk set.</p>
        </div>
        <Button type="button" onClick={() => setOpen(true)}>Build BM25 artifact</Button>
      </div>

      {artifacts.isError ? <div className="mt-4"><ErrorState message="Unable to load BM25 artifacts." onRetry={() => artifacts.refetch()} /></div> : null}
      <div className="mt-4 grid gap-3">
        {(artifacts.data ?? []).map((artifact) => {
          const chunkSet = setsById.get(artifact.corpus_chunk_set_id);
          return <div id={`bm25-artifact-${artifact.id}`} key={artifact.id} className="rounded-xl bg-slate-50 p-3">
            <div className="flex items-center justify-between gap-3"><strong>{artifact.name}</strong><StatusBadge status={artifact.status} /></div>
            <p className="mt-2 text-sm text-slate-600">Artifact #{artifact.id} · {chunkSet?.name ?? `Set #${artifact.corpus_chunk_set_id}`} · Indexed chunks: {artifact.document_count}</p>
            <p className="mt-1 text-xs text-slate-500">Set revision {artifact.corpus_chunk_set_revision} · Snapshot {artifact.document_chunk_ids_checksum.slice(0, 12)}… · {formatDateTime(artifact.built_at ?? artifact.created_at)}</p>
            {artifact.build_error ? <p className="mt-2 text-sm text-red-700">{artifact.build_error}</p> : null}
          </div>;
        })}
        {!artifacts.isLoading && !artifacts.isError && !(artifacts.data ?? []).length ? <p className="text-sm text-slate-600">No BM25 artifacts linked to this corpus yet.</p> : null}
      </div>

      {(jobs.data ?? []).length ? <div className="mt-5 border-t border-slate-200 pt-4"><h3 className="font-medium text-slate-950">Build jobs</h3><div className="mt-3 grid gap-2">
        {(jobs.data ?? []).map((job) => <div key={job.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 p-3"><div><span className="font-medium">{job.requested_artifact_name}</span><p className="text-xs text-slate-500">Job #{job.id} · {job.stage}</p>{job.failure_detail ? <p className="mt-1 text-sm text-red-700">{job.failure_detail}</p> : null}</div><div className="flex items-center gap-2"><StatusBadge status={job.status} />{job.status === "queued" || job.status === "running" ? <Button variant="secondary" onClick={() => cancel.mutateAsync(job.id)}>Cancel</Button> : null}{job.status === "failed" || job.status === "cancelled" ? <Button variant="secondary" onClick={() => { setRetryJobId(job.id); setName(""); setNameEdited(true); setOpen(true); }}>Retry</Button> : null}</div></div>)}
      </div></div> : null}

      {open ? <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/45 p-4"><Card className="w-full max-w-xl">
        <div className="flex justify-between gap-3"><div><h3 className="text-lg font-semibold">{retryJobId === null ? "Build BM25 artifact" : "Retry BM25 build"}</h3><p className="mt-1 text-sm text-slate-600">{retryJobId === null ? "Choose an existing named chunk set." : "Choose a new unique artifact name."}</p></div><Button variant="ghost" onClick={closeModal}>Close</Button></div>
        {retryJobId === null && chunkSets.isError ? <div className="mt-4"><ErrorState message="Unable to load corpus chunk sets." onRetry={() => chunkSets.refetch()} /></div> : retryJobId === null && !(chunkSets.data ?? []).length && !chunkSets.isLoading ? <div className="mt-5 rounded-xl bg-amber-50 p-4 text-sm text-amber-950"><p>BM25 requires persisted chunks in a named set. Create one using the Full Corpus Index Pipe.</p><Link className="mt-3 inline-block font-medium underline" to="/full-corpus-index-pipe-jobs">Open Full Corpus Index Pipe</Link></div> : <form className="mt-5 grid gap-4" onSubmit={async (event) => { event.preventDefault(); setError(null); try { if (retryJobId === null) await queue.mutateAsync({ requested_artifact_name: name.trim(), corpus_chunk_set_id: Number(chunkSetId) }); else await retry.mutateAsync({ jobId: retryJobId, requestedArtifactName: name.trim() }); closeModal(); } catch (caught) { setError(getErrorMessage(caught, "Unable to queue BM25 build.")); } }}>
          {retryJobId === null ? <Field label="Chunk set"><Select value={chunkSetId} onChange={(event) => { const value = event.target.value; setChunkSetId(value); const selected = (chunkSets.data ?? []).find((item) => String(item.id) === value); if (selected && !nameEdited) setName(`${corpusName} BM25 - ${selected.name}`); }}><option value="">Select a persisted chunk set</option>{(chunkSets.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.name} · {item.chunking_profile_name} · revision {item.revision} · {item.distinct_document_count} documents · {item.chunk_count} chunks</option>)}</Select></Field> : null}
          <Field label="Artifact name"><Input value={name} onChange={(event) => { setName(event.target.value); setNameEdited(true); }} /></Field>
          {nameAvailability.data?.available === false ? <p role="alert" className="text-sm text-red-700">{nameAvailability.data.reason}</p> : null}
          {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
          <div className="flex justify-end"><Button type="submit" disabled={(retryJobId === null && !chunkSetId) || name.trim().length < 3 || nameAvailability.data?.available === false || queue.isPending || retry.isPending}>{queue.isPending || retry.isPending ? "Queueing..." : "Queue BM25 build"}</Button></div>
        </form>}
      </Card></div> : null}
    </Card>
  );
}
