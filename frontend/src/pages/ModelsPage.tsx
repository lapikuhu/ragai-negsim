import {
  useChunkingProfilesQuery,
  useCorpusIndicesQuery,
  useEmbeddingModelsQuery,
  useVectorStoresQuery
} from "@/features/models/modelQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/common/StatusBadge";

export function ModelsPage() {
  const embeddings = useEmbeddingModelsQuery();
  const vectorStores = useVectorStoresQuery();
  const chunkingProfiles = useChunkingProfilesQuery();
  const indices = useCorpusIndicesQuery();

  if ([embeddings, vectorStores, chunkingProfiles, indices].some((query) => query.isLoading)) {
    return <LoadingState label="Loading models and stores..." />;
  }

  const error = [embeddings, vectorStores, chunkingProfiles, indices].find((query) => query.isError)?.error;
  if (error) {
    return <ErrorState message={error.message} />;
  }

  return (
    <div className="grid gap-6">
      <PageHeader title="Models and stores" description="Embedding models, vector stores, chunking profiles, and corpus indices exposed by the backend." />

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <h2 className="text-lg font-semibold text-slate-950">Embedding models</h2>
          <div className="mt-4 grid gap-3">
            {(embeddings.data ?? []).map((model) => (
              <div key={model.name} className="rounded-xl bg-slate-50 p-3">
                <strong>{model.display_name}</strong>
                <p className="mt-1 text-sm text-slate-600">
                  Provider: {model.provider} · Dimensions: {model.dimensionality} · Normalized: {model.normalized ? "yes" : "no"}
                </p>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold text-slate-950">Vector stores</h2>
          <div className="mt-4 grid gap-3">
            {(vectorStores.data ?? []).map((store) => (
              <div key={store.id} className="rounded-xl bg-slate-50 p-3">
                <strong>{store.name}</strong>
                <p className="mt-1 text-sm text-slate-600">Backend: {store.backend}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold text-slate-950">Chunking profiles</h2>
          <div className="mt-4 grid gap-3">
            {(chunkingProfiles.data ?? []).map((profile) => (
              <div key={profile.id} className="rounded-xl bg-slate-50 p-3">
                <strong>{profile.name}</strong>
                <p className="mt-1 text-sm text-slate-600">Strategy: {profile.strategy}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold text-slate-950">Corpus indices</h2>
          <div className="mt-4 grid gap-3">
            {(indices.data ?? []).map((index) => (
              <div key={index.id} className="rounded-xl bg-slate-50 p-3">
                <div className="flex items-center justify-between gap-3">
                  <strong>{index.name}</strong>
                  <StatusBadge status={index.status} />
                </div>
                <p className="mt-1 text-sm text-slate-600">Model: {index.embedding_model}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
