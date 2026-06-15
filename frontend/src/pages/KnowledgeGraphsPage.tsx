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

const graphExtractors = ["simple", "implicit", "schema"] as const;

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
    extractors: ["schema"] as Array<(typeof graphExtractors)[number]>,
  });

  if (graphs.isLoading) {
    return <LoadingState label="Loading knowledge graphs..." />;
  }
  if (graphs.isError) {
    return <ErrorState message={graphs.error.message} onRetry={() => graphs.refetch()} />;
  }

  const items = graphs.data ?? [];
  const builtIndices = (indices.data ?? []).filter((index) => index.status === "built");

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Knowledge Graphs"
        description="Build reusable Neo4j GraphRAG indexes from the exact chunks in an existing corpus index."
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
                  extractors: form.extractors,
                  strict_schema: true,
                  max_paths_per_chunk: 10,
                },
              });
              setForm((current) => ({ ...current, name: "", corpusIndexId: "" }));
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
            <legend className="text-sm font-medium text-slate-700">Extractors</legend>
            <div className="mt-2 flex flex-wrap gap-4">
              {graphExtractors.map((extractor) => (
                <label key={extractor} className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={form.extractors.includes(extractor)}
                    onChange={(event) => {
                      setForm((current) => ({
                        ...current,
                        extractors: event.target.checked
                          ? [...current.extractors, extractor]
                          : current.extractors.filter((value) => value !== extractor),
                      }));
                    }}
                  />
                  {extractor[0].toUpperCase() + extractor.slice(1)}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="md:col-span-2 flex items-center gap-3">
            <Button type="submit" disabled={createMutation.isPending || !form.extractors.length}>Create graph</Button>
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
