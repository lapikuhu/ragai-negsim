import { useMemo } from "react";
import { useParams } from "react-router-dom";
import { useCorporaQuery } from "@/features/corpora/corpusQueries";
import { useCorpusIndicesQuery } from "@/features/corpusIndices/corpusIndexQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { Card } from "@/components/ui/Card";
import { KeyValueList } from "@/components/common/KeyValueList";
import { StatusBadge } from "@/components/common/StatusBadge";
import { formatDateTime } from "@/utils/format";

export function CorpusDetailPage() {
  const corpusId = Number(useParams().corpusId);
  const corpora = useCorporaQuery();
  const indices = useCorpusIndicesQuery();

  const corpus = useMemo(() => (corpora.data ?? []).find((item) => item.id === corpusId), [corpora.data, corpusId]);
  const relatedIndices = useMemo(
    () => (indices.data ?? []).filter((index) => index.corpus_id === corpusId),
    [corpusId, indices.data]
  );

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
        <h2 className="text-lg font-semibold text-slate-950">Indexing workflow</h2>
        <p className="mt-3 text-sm text-slate-600">
          Corpus ingestion, cleaning, chunking, embedding, and replacement now run through the central admin Indexing page.
          Use that page to queue a full build, monitor progress, and review warnings or failures.
        </p>
      </Card>

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
