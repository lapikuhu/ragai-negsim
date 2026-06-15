import { useState } from "react";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { DataTable } from "@/components/common/DataTable";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { getErrorMessage } from "@/api/client";
import { formatDateTime } from "@/utils/format";
import { useCorpusIndicesQuery } from "@/features/corpusIndices/corpusIndexQueries";
import {
  useBuildKnowledgeGraphMutation,
  useCreateKnowledgeGraphMutation,
  useDeleteKnowledgeGraphMutation,
  useKnowledgeGraphsQuery,
} from "@/features/knowledgeGraphs/knowledgeGraphQueries";

const semanticExtractors = ["schema", "simple"] as const;
type SemanticExtractor = (typeof semanticExtractors)[number];
type GraphExtractor = SemanticExtractor | "implicit";

const semanticExtractorCopy: Record<
  SemanticExtractor,
  { title: string; description: string }
> = {
  schema: {
    title: "Schema",
    description:
      "Extracts typed negotiation concepts and relationships constrained by the ontology. Recommended for consistent GraphRAG behavior.",
  },
  simple: {
    title: "Simple",
    description:
      "Uses the LLM to extract unrestricted subject-relation-object triples. More flexible, but less predictable.",
  },
};

export function KnowledgeGraphsPage() {
  const graphs = useKnowledgeGraphsQuery();
  const indices = useCorpusIndicesQuery();
  const createMutation = useCreateKnowledgeGraphMutation();
  const buildMutation = useBuildKnowledgeGraphMutation();
  const deleteMutation = useDeleteKnowledgeGraphMutation();
  const [message, setMessage] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    corpusIndexId: "",
    llmProvider: "openai",
    llmModel: "gpt-4o-mini",
    embeddingProvider: "openai",
    embeddingModel: "text-embedding-3-small",
    semanticExtractor: "schema" as SemanticExtractor,
    includeImplicit: true,
  });

  if (graphs.isLoading) {
    return <LoadingState label="Loading knowledge graphs..." />;
  }
  if (graphs.isError) {
    return <ErrorState message={graphs.error.message} onRetry={() => graphs.refetch()} />;
  }

  const items = graphs.data ?? [];
  const builtIndices = (indices.data ?? []).filter((index) => index.status === "built");
  const selectedExtractors: GraphExtractor[] = form.includeImplicit
    ? [form.semanticExtractor, "implicit"]
    : [form.semanticExtractor];

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Knowledge Graphs"
        description="Build reusable Neo4j GraphRAG indexes from the exact chunks in an existing corpus index. Careful, token expensive."
      />
      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Create graph definition</h2>
        <form
          className="mt-4 grid gap-3 md:grid-cols-2"
          onSubmit={async (event) => {
            event.preventDefault();
            setMessage(null);
            try {
              await createMutation.mutateAsync({
                name: form.name.trim(),
                corpus_index_id: Number(form.corpusIndexId),
                build_config: {
                  llm_provider: form.llmProvider as "openai" | "ollama",
                  llm_model: form.llmModel.trim(),
                  embedding_provider: form.embeddingProvider as "openai" | "ollama",
                  embedding_model: form.embeddingModel.trim(),
                  extractors: selectedExtractors,
                  strict_schema: true,
                  max_paths_per_chunk: 10,
                },
              });
              setForm((current) => ({
                ...current,
                name: "",
                corpusIndexId: "",
                semanticExtractor: "schema",
                includeImplicit: true,
              }));
              setMessage("Knowledge graph definition created.");
            } catch (error) {
              setMessage(getErrorMessage(error, "Unable to create knowledge graph"));
            }
          }}
        >
          <Field label="Name">
            <Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
          </Field>
          <Field label="Built corpus index">
            <Select
              value={form.corpusIndexId}
              onChange={(event) => setForm({ ...form, corpusIndexId: event.target.value })}
              required
            >
              <option value="">Select index</option>
              {builtIndices.map((index) => (
                <option key={index.id} value={index.id}>{index.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Extraction provider">
            <Select
              value={form.llmProvider}
              onChange={(event) => setForm({ ...form, llmProvider: event.target.value })}
            >
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama</option>
            </Select>
          </Field>
          <Field label="Extraction model">
            <Input value={form.llmModel} onChange={(event) => setForm({ ...form, llmModel: event.target.value })} required />
          </Field>
          <Field label="Embedding provider">
            <Select
              value={form.embeddingProvider}
              onChange={(event) => setForm({ ...form, embeddingProvider: event.target.value })}
            >
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama</option>
            </Select>
          </Field>
          <Field label="Embedding model">
            <Input
              value={form.embeddingModel}
              onChange={(event) => setForm({ ...form, embeddingModel: event.target.value })}
              required
            />
          </Field>
          <fieldset className="md:col-span-2">
            <legend className="text-sm font-medium text-slate-700">Semantic extraction</legend>
            <p className="mt-1 text-xs text-slate-500">
              Pick one semantic strategy. Chunk structure can be layered on separately below.
            </p>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {semanticExtractors.map((extractor) => (
                <label
                  key={extractor}
                  className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-sm text-slate-700"
                >
                  <input
                    type="radio"
                    name="semantic-extractor"
                    className="mt-0.5 h-4 w-4 shrink-0"
                    checked={form.semanticExtractor === extractor}
                    onChange={() => setForm((current) => ({ ...current, semanticExtractor: extractor }))}
                  />
                  <span className="grid gap-2">
                    <span className="font-medium text-slate-950">
                      {semanticExtractorCopy[extractor].title}
                    </span>
                    <span className="text-xs leading-5 text-slate-600">
                      {semanticExtractorCopy[extractor].description}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset className="md:col-span-2">
            <legend className="text-sm font-medium text-slate-700">Structure</legend>
            <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
              <label className="flex items-start gap-3 text-sm text-slate-700">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 shrink-0"
                  checked={form.includeImplicit}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      includeImplicit: event.target.checked,
                    }))
                  }
                />
                <span>
                  <span className="font-medium text-slate-950">Include chunk structure</span>
                  <span className="mt-1 block text-xs leading-5 text-slate-600">
                    Adds existing document relationships such as previous and next chunks. This
                    does not extract semantic entities or add more LLM calls.
                  </span>
                </span>
              </label>
            </div>
          </fieldset>
          <div className="md:col-span-2 flex items-center gap-3">
            <Button type="submit" disabled={createMutation.isPending}>Create graph</Button>
            {message ? <span className="text-sm text-slate-600">{message}</span> : null}
          </div>
        </form>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Graph indexes</h2>
        {items.length ? (
          <div className="mt-4">
            <DataTable
              rows={items}
              columns={[
                {
                  key: "name",
                  header: "Graph",
                  render: (graph) => (
                    <div>
                      <div className="font-medium text-slate-950">{graph.name}</div>
                      <div className="mt-1 text-xs text-slate-500">Corpus index #{graph.corpus_index_id}</div>
                    </div>
                  ),
                },
                {
                  key: "status",
                  header: "Status",
                  render: (graph) => (
                    <div>
                      <div className="capitalize">{graph.status}</div>
                      {graph.latest_build_error ? (
                        <div className="mt-1 max-w-sm text-xs text-red-700">
                          {graph.latest_build_error}
                        </div>
                      ) : null}
                    </div>
                  ),
                },
                {
                  key: "models",
                  header: "Models",
                  render: (graph) => (
                    <div className="text-xs text-slate-600">
                      <div>{graph.build_config.llm_provider}: {graph.build_config.llm_model}</div>
                      <div>{graph.build_config.embedding_provider}: {graph.build_config.embedding_model}</div>
                    </div>
                  ),
                },
                {
                  key: "lock",
                  header: "Usage",
                  render: (graph) => graph.locked_at ? (
                    <div>
                      <div className="font-medium text-amber-700">Permanently locked</div>
                      <div className="text-xs text-slate-500">{graph.simulation_ids.length} simulations</div>
                    </div>
                  ) : "Unused",
                },
                {
                  key: "updated",
                  header: "Updated",
                  render: (graph) => formatDateTime(graph.last_updated),
                },
                {
                  key: "actions",
                  header: "Actions",
                  render: (graph) => (
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={Boolean(graph.active_job_id) || (Boolean(graph.active_generation) && Boolean(graph.locked_at))}
                        onClick={() => buildMutation.mutate({
                          graphId: graph.id,
                          rebuild: Boolean(graph.active_generation),
                        })}
                      >
                        {graph.active_generation ? "Rebuild" : "Build"}
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        disabled={Boolean(graph.locked_at) || Boolean(graph.active_job_id) || graph.rag_profile_ids.length > 0}
                        onClick={() => deleteMutation.mutate(graph.id)}
                      >
                        Delete
                      </Button>
                    </div>
                  ),
                },
              ]}
            />
          </div>
        ) : (
          <div className="mt-4">
            <EmptyState title="No knowledge graphs" description="Create a graph definition from a built corpus index." />
          </div>
        )}
      </Card>
    </div>
  );
}
