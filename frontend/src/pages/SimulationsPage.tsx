import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  useCreateSimulationMutation,
  useSimulationRetrievalOptionsQuery,
  useSimulationsQuery,
} from "@/features/simulations/simulationQueries";
import {
  filterRetrievalOptions,
  reconcileRetrievalSelection,
} from "@/features/simulations/simulationRetrievalOptions";
import { useCorporaQuery } from "@/features/corpora/corpusQueries";
import {
  useCorpusIndicesQuery,
  useChunkingProfilesQuery,
  useVectorStoresQuery
} from "@/features/corpusIndices/corpusIndexQueries";
import { useRagProfilesQuery } from "@/features/ragProfiles/ragProfileQueries";
import { useKnowledgeGraphsQuery } from "@/features/knowledgeGraphs/knowledgeGraphQueries";
import { useScenariosQuery } from "@/features/scenarios/scenarioQueries";
import { usePersonasQuery } from "@/features/counterpartPersonas/personaQueries";
import { usePromptsQuery } from "@/features/prompts/promptQueries";
import { useSessionsQuery } from "@/features/sessions/sessionQueries";
import { useUsersQuery } from "@/features/users/userQueries";
import { useLlmModelCatalogQuery } from "@/features/llmModels/llmModelQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { DataTable } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { LlmModelSelector, getDefaultCatalogModel } from "@/components/llm/LlmModelSelector";
import { formatDateTime } from "@/utils/format";
import { ApiError, getErrorMessage } from "@/api/client";
import type { LLMSelection } from "@/api/types";

export function SimulationsPage() {
  const query = useSimulationsQuery();
  const corpora = useCorporaQuery();
  const indices = useCorpusIndicesQuery();
  useChunkingProfilesQuery();
  useVectorStoresQuery();
  const ragProfiles = useRagProfilesQuery();
  const knowledgeGraphs = useKnowledgeGraphsQuery();
  const scenarios = useScenariosQuery();
  const personas = usePersonasQuery();
  const prompts = usePromptsQuery();
  const sessions = useSessionsQuery();
  const users = useUsersQuery();
  const llmCatalogQuery = useLlmModelCatalogQuery();
  const createMutation = useCreateSimulationMutation();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    name: "",
    description: "",
    corpusId: "",
    corpusIndexId: "",
    bm25IndexId: "",
    ragProfileId: "",
    scenarioId: "",
    personaId: "",
    coachPromptId: "",
    counterpartPromptId: "",
    evaluatorPromptId: "",
    sessionId: "",
    participantId: "",
    userSide: "side_a",
    useLearnerAgent: false,
    learnerTavilyMaxResults: "5",
    learnerTavilyIncludeImages: false,
    learnerTavilyIncludeAnswers: false
  });
  const [learnerResponseLlm, setLearnerResponseLlm] = useState<LLMSelection>({ provider: "openai", model: "" });
  const [learnerSummaryLlm, setLearnerSummaryLlm] = useState<LLMSelection>({ provider: "openai", model: "" });
  const [learnerTavilySummaryLlm, setLearnerTavilySummaryLlm] = useState<LLMSelection>({ provider: "openai", model: "" });
  const [message, setMessage] = useState<string | null>(null);

  const corpusOptions = corpora.data ?? [];
  const ragProfileOptions = ragProfiles.data ?? [];
  const selectedRagProfile = ragProfileOptions.find((profile) => String(profile.id) === form.ragProfileId);
  const isCragProfile = selectedRagProfile?.strategy === "crag";
  const retrievalOptions = useSimulationRetrievalOptionsQuery(
    form.corpusId ? Number(form.corpusId) : undefined,
    form.ragProfileId ? Number(form.ragProfileId) : undefined,
    isCragProfile,
  );
  const retrievalMode = isCragProfile
    ? retrievalOptions.data?.mode ?? null
    : selectedRagProfile?.strategy === "graphrag" ? "dense" : null;
  const needsDenseIndex = retrievalMode === "dense" || retrievalMode === "hybrid";
  const needsBm25Index = retrievalMode === "bm25" || retrievalMode === "hybrid";
  const selectedKnowledgeGraph = (knowledgeGraphs.data ?? []).find(
    (graph) => graph.id === selectedRagProfile?.knowledge_graph_index_id,
  );
  const graphCorpusIndex = (indices.data ?? []).find(
    (index) => index.id === selectedKnowledgeGraph?.corpus_index_id,
  );
  const graphSelectionLocked = selectedRagProfile?.strategy === "graphrag" && Boolean(graphCorpusIndex);
  const graphIndexOptions = useMemo(
    () => (indices.data ?? []).filter(
      (index) => (String(index.corpus_id) === form.corpusId || !form.corpusId) && index.status === "built",
    ),
    [form.corpusId, indices.data]
  );
  const filteredRetrievalOptions = retrievalOptions.data
    ? filterRetrievalOptions(
        retrievalOptions.data,
        form.corpusIndexId,
        form.bm25IndexId,
      )
    : { dense: [], bm25: [] };
  const indexOptions = isCragProfile
    ? filteredRetrievalOptions.dense
    : graphIndexOptions;
  const bm25IndexOptions = filteredRetrievalOptions.bm25;
  const retrievalOptionsEnabled = Boolean(
    isCragProfile && form.corpusId && form.ragProfileId,
  );
  const retrievalOptionsUnavailable = retrievalOptionsEnabled
    && (retrievalOptions.isLoading || retrievalOptions.isError);
  const retrievalSelectionComplete = !isCragProfile || Boolean(
    retrievalOptions.data
    && (!needsDenseIndex || form.corpusIndexId)
    && (!needsBm25Index || form.bm25IndexId)
  );

  useEffect(() => {
    if (!graphCorpusIndex) {
      return;
    }
    setForm((current) => {
      const corpusId = String(graphCorpusIndex.corpus_id);
      const corpusIndexId = String(graphCorpusIndex.id);
      if (current.corpusId === corpusId && current.corpusIndexId === corpusIndexId) {
        return current;
      }
      return { ...current, corpusId, corpusIndexId };
    });
  }, [graphCorpusIndex]);

  useEffect(() => {
    if (!isCragProfile || !retrievalOptions.data) {
      return;
    }
    setForm((current) => {
      const reconciled = reconcileRetrievalSelection(
        retrievalOptions.data,
        {
          corpusIndexId: current.corpusIndexId,
          bm25IndexId: current.bm25IndexId,
        },
        "refresh",
      );
      if (
        reconciled.corpusIndexId === current.corpusIndexId
        && reconciled.bm25IndexId === current.bm25IndexId
      ) {
        return current;
      }
      return { ...current, ...reconciled };
    });
  }, [isCragProfile, retrievalOptions.data]);

  useEffect(() => {
    const defaultModel = getDefaultCatalogModel(llmCatalogQuery.data, "openai");
    if (!defaultModel) {
      return;
    }
    setLearnerResponseLlm((current) => current.model ? current : { provider: "openai", model: defaultModel });
    setLearnerSummaryLlm((current) => current.model ? current : { provider: "openai", model: defaultModel });
    setLearnerTavilySummaryLlm((current) => current.model ? current : { provider: "openai", model: defaultModel });
  }, [llmCatalogQuery.data]);

  const canSubmitLearnerConfig =
    !form.useLearnerAgent ||
    Boolean(learnerResponseLlm.model && learnerSummaryLlm.model && learnerTavilySummaryLlm.model);

  return (
    <div className="grid gap-6">
      <PageHeader title="Simulations" description="Primary negotiation workflow from the `/simulations` domain." />

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Create simulation</h2>
        <form
          className="mt-4 grid gap-3 md:grid-cols-2"
          onSubmit={async (event) => {
            event.preventDefault();
            setMessage(null);
            try {
              const learnerPayload = form.useLearnerAgent
                ? {
                    use_learner_agent: true,
                    learner_response_llm_provider: learnerResponseLlm.provider,
                    learner_response_llm_model: learnerResponseLlm.model,
                    learner_summary_llm_provider: learnerSummaryLlm.provider,
                    learner_summary_llm_model: learnerSummaryLlm.model,
                    learner_tavily_summary_llm_provider: learnerTavilySummaryLlm.provider,
                    learner_tavily_summary_llm_model: learnerTavilySummaryLlm.model,
                    learner_tavily_max_results: Number(form.learnerTavilyMaxResults || "5"),
                    learner_tavily_include_images: form.learnerTavilyIncludeImages,
                    learner_tavily_include_answers: form.learnerTavilyIncludeAnswers
                  }
                : {
                    use_learner_agent: false,
                    learner_tavily_max_results: Number(form.learnerTavilyMaxResults || "5"),
                    learner_tavily_include_images: false,
                    learner_tavily_include_answers: false
                  };
              const simulation = await createMutation.mutateAsync({
                name: form.name,
                description: form.description || null,
                corpus_id: Number(form.corpusId),
                corpus_index_id: needsDenseIndex && form.corpusIndexId ? Number(form.corpusIndexId) : null,
                bm25_index_id: needsBm25Index && form.bm25IndexId ? Number(form.bm25IndexId) : null,
                rag_profile_id: Number(form.ragProfileId),
                coach_prompt_id: form.coachPromptId ? Number(form.coachPromptId) : null,
                counterpart_prompt_id: form.counterpartPromptId ? Number(form.counterpartPromptId) : null,
                evaluator_prompt_id: form.evaluatorPromptId ? Number(form.evaluatorPromptId) : null,
                session_id: form.sessionId ? Number(form.sessionId) : null,
                user_id_participant: form.participantId ? Number(form.participantId) : null,
                scenario_id: form.scenarioId ? Number(form.scenarioId) : null,
                counter_part_side_persona_id: form.personaId ? Number(form.personaId) : null,
                user_side: form.userSide === "side_b" ? "side_b" : "side_a",
                ...learnerPayload
              });
              navigate(`/simulations/${simulation.id}`);
            } catch (error) {
              setMessage(getErrorMessage(error));
              if (
                error instanceof ApiError
                && error.status === 409
                && isCragProfile
              ) {
                await retrievalOptions.refetch();
              }
            }
          }}
        >
          <Field label="Name">
            <Input
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              required
            />
          </Field>
          <Field label="Corpus">
            <Select
              value={form.corpusId}
              onChange={(event) => setForm((current) => ({
                ...current,
                corpusId: event.target.value,
                corpusIndexId: "",
                bm25IndexId: "",
              }))}
              disabled={graphSelectionLocked}
              required
            >
              <option value="">Select corpus</option>
              {corpusOptions.map((corpus) => (
                <option key={corpus.id} value={corpus.id}>
                  {corpus.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Description" hint="Optional">
            <Textarea
              value={form.description}
              onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
            />
          </Field>
          <Field label="RAG profile" hint={ragProfileOptions.length ? "Required" : "Create one from the admin RAG Profiles page first."}>
            <Select
              value={form.ragProfileId}
              onChange={(event) => setForm((current) => ({
                ...current,
                ragProfileId: event.target.value,
                corpusIndexId: "",
                bm25IndexId: "",
              }))}
              required
            >
              <option value="">{ragProfileOptions.length ? "Select RAG profile" : "No RAG profiles available"}</option>
              {ragProfileOptions.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </Select>
          </Field>

          {needsDenseIndex ? (
            <Field
              label="Corpus index"
              className="self-start"
            >
              <Select
                className="min-h-10 leading-5"
                value={form.corpusIndexId}
                onChange={(event) => setForm((current) => {
                  const selection = {
                    corpusIndexId: event.target.value,
                    bm25IndexId: current.bm25IndexId,
                  };
                  return {
                    ...current,
                    ...(isCragProfile && retrievalOptions.data
                      ? reconcileRetrievalSelection(
                          retrievalOptions.data,
                          selection,
                          "dense",
                        )
                      : selection),
                  };
                })}
                disabled={graphSelectionLocked || retrievalOptionsUnavailable}
                required
              >
                <option value="">Select built corpus index</option>
                {indexOptions.map((index) => (
                  <option key={index.id} value={index.id}>{index.name}</option>
                ))}
              </Select>
            </Field>
          ) : null}
          {needsBm25Index ? (
            <>
              <Field
                label="BM25 index"
                className="self-start"
              >
                <Select
                  className="min-h-10 leading-5"
                  value={form.bm25IndexId}
                  disabled={retrievalOptionsUnavailable}
                  onChange={(event) => setForm((current) => {
                    const selection = {
                      corpusIndexId: current.corpusIndexId,
                      bm25IndexId: event.target.value,
                    };
                    return {
                      ...current,
                      ...(retrievalOptions.data
                        ? reconcileRetrievalSelection(
                            retrievalOptions.data,
                            selection,
                            "bm25",
                          )
                        : selection),
                    };
                  })}
                  required
                >
                  <option value="">Select built BM25 index</option>
                  {bm25IndexOptions.map((index) => (
                    <option key={index.id} value={index.id}>{index.name}</option>
                  ))}
                </Select>
              </Field>
            </>
          ) : null}

          {retrievalOptionsEnabled && retrievalOptions.isLoading ? (
            <p className="self-start text-sm text-slate-500">Loading retrieval options...</p>
          ) : null}
          {retrievalOptionsEnabled
            && !retrievalOptions.isLoading
            && !retrievalOptions.isError
            && retrievalOptions.data?.mode === "dense"
            && !(retrievalOptions.data.dense_indices ?? []).length ? (
              <p className="self-start text-sm text-amber-700">A built dense index is required.</p>
            ) : null}
          {retrievalOptionsEnabled
            && !retrievalOptions.isLoading
            && !retrievalOptions.isError
            && retrievalOptions.data?.mode === "bm25"
            && !(retrievalOptions.data.bm25_indices ?? []).length ? (
              <p className="self-start text-sm text-amber-700">A built BM25 artifact is required.</p>
            ) : null}
          {retrievalOptionsEnabled
            && !retrievalOptions.isLoading
            && !retrievalOptions.isError
            && retrievalOptions.data?.mode === "hybrid"
            && !(retrievalOptions.data.compatible_pairs ?? []).length ? (
              <p className="self-start text-sm text-amber-700">No compatible dense/BM25 pair exists.</p>
            ) : null}
          {retrievalOptionsEnabled && retrievalOptions.isError ? (
            <div role="alert" className="self-start text-sm text-red-700">
              <p>{getErrorMessage(retrievalOptions.error, "Unable to load retrieval options")}</p>
              <Button type="button" variant="secondary" onClick={() => retrievalOptions.refetch()}>
                Retry retrieval options
              </Button>
            </div>
          ) : null}

          <Field label="Scenario" className="self-start">
            <Select
              value={form.scenarioId}
              onChange={(event) => setForm((current) => ({ ...current, scenarioId: event.target.value }))}
            >
              <option value="">Optional</option>
              {(scenarios.data ?? []).map((scenario) => (
                <option key={scenario.id} value={scenario.id}>
                  {scenario.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Counterpart persona">
            <Select
              value={form.personaId}
              onChange={(event) => setForm((current) => ({ ...current, personaId: event.target.value }))}
            >
              <option value="">Optional</option>
              {(personas.data ?? []).map((persona) => (
                <option key={persona.id} value={persona.id}>
                  {persona.name}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Coach prompt">
            <Select
              value={form.coachPromptId}
              onChange={(event) => setForm((current) => ({ ...current, coachPromptId: event.target.value }))}
            >
              <option value="">Optional</option>
              {(prompts.data ?? []).map((prompt) => (
                <option key={prompt.id} value={prompt.id}>
                  {prompt.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Counterpart prompt">
            <Select
              value={form.counterpartPromptId}
              onChange={(event) => setForm((current) => ({ ...current, counterpartPromptId: event.target.value }))}
            >
              <option value="">Optional</option>
              {(prompts.data ?? []).map((prompt) => (
                <option key={prompt.id} value={prompt.id}>
                  {prompt.name}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Evaluator prompt">
            <Select
              value={form.evaluatorPromptId}
              onChange={(event) => setForm((current) => ({ ...current, evaluatorPromptId: event.target.value }))}
            >
              <option value="">Optional</option>
              {(prompts.data ?? []).map((prompt) => (
                <option key={prompt.id} value={prompt.id}>
                  {prompt.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="User side">
            <Select
              value={form.userSide}
              onChange={(event) => setForm((current) => ({ ...current, userSide: event.target.value }))}
            >
              <option value="side_a">side_a</option>
              <option value="side_b">side_b</option>
            </Select>
          </Field>

          <Field label="Linked user session">
            <Select
              value={form.sessionId}
              onChange={(event) => setForm((current) => ({ ...current, sessionId: event.target.value }))}
            >
              <option value="">Optional</option>
              {(sessions.data ?? []).map((session) => (
                <option key={session.id} value={session.id}>
                  Session #{session.id}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Participant user">
            <Select
              value={form.participantId}
              onChange={(event) => setForm((current) => ({ ...current, participantId: event.target.value }))}
            >
              <option value="">Optional</option>
              {(users.data ?? []).map((user) => (
                <option key={user.id} value={user.id}>
                  {user.username}
                </option>
              ))}
            </Select>
          </Field>

          <div className="md:col-span-2 grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
            <label className="flex items-center gap-2 text-sm font-medium text-slate-800">
              <input
                type="checkbox"
                checked={form.useLearnerAgent}
                onChange={(event) => setForm((current) => ({ ...current, useLearnerAgent: event.target.checked }))}
              />
              <span>Use Learning Agent</span>
            </label>
            {form.useLearnerAgent ? (
              <div className="grid gap-3">
                <div className="grid gap-3 lg:grid-cols-3">
                  <LlmModelSelector
                    label="Learner response LLM"
                    catalog={llmCatalogQuery.data}
                    selection={learnerResponseLlm}
                    onChange={setLearnerResponseLlm}
                    disabled={llmCatalogQuery.isLoading || createMutation.isPending}
                    metadataMode="error-only"
                  />
                  <LlmModelSelector
                    label="Negotiation summary LLM"
                    catalog={llmCatalogQuery.data}
                    selection={learnerSummaryLlm}
                    onChange={setLearnerSummaryLlm}
                    disabled={llmCatalogQuery.isLoading || createMutation.isPending}
                    metadataMode="error-only"
                  />
                  <LlmModelSelector
                    label="Tavily summary LLM"
                    catalog={llmCatalogQuery.data}
                    selection={learnerTavilySummaryLlm}
                    onChange={setLearnerTavilySummaryLlm}
                    disabled={llmCatalogQuery.isLoading || createMutation.isPending}
                    metadataMode="error-only"
                  />
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  <Field label="Tavily max results">
                    <Input
                      type="number"
                      min={1}
                      value={form.learnerTavilyMaxResults}
                      onChange={(event) => setForm((current) => ({ ...current, learnerTavilyMaxResults: event.target.value }))}
                    />
                  </Field>
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={form.learnerTavilyIncludeImages}
                      onChange={(event) => setForm((current) => ({ ...current, learnerTavilyIncludeImages: event.target.checked }))}
                    />
                    <span>Include Tavily images</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={form.learnerTavilyIncludeAnswers}
                      onChange={(event) => setForm((current) => ({ ...current, learnerTavilyIncludeAnswers: event.target.checked }))}
                    />
                    <span>Include Tavily answer</span>
                  </label>
                </div>
                {llmCatalogQuery.isLoading ? <p className="text-sm text-slate-500">Loading models...</p> : null}
                {llmCatalogQuery.isError ? <p className="text-sm text-amber-700">LLM catalog is unavailable.</p> : null}
              </div>
            ) : null}
          </div>

          <div className="md:col-span-2 flex items-center gap-3">
            <Button
              type="submit"
              disabled={
                createMutation.isPending
                || !ragProfileOptions.length
                || !canSubmitLearnerConfig
                || retrievalOptionsUnavailable
                || !retrievalSelectionComplete
              }
            >
              {createMutation.isPending ? "Creating..." : "Create simulation"}
            </Button>
            {message ? <span className="text-sm text-red-700">{message}</span> : null}
            {!ragProfileOptions.length ? <span className="text-sm text-amber-700">An admin must create a RAG profile before simulations can be started.</span> : null}
          </div>
        </form>
      </Card>

      {query.isLoading ? (
        <LoadingState label="Loading simulations..." />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => query.refetch()} />
      ) : query.data?.length ? (
        <DataTable
          rows={query.data}
          columns={[
            {
              key: "name",
              header: "Simulation",
              render: (simulation) => (
                <div>
                  <Link className="font-medium text-accent" to={`/simulations/${simulation.id}`}>
                    {simulation.name}
                  </Link>
                  <p className="mt-1 text-xs text-slate-500">{simulation.description ?? "No description"}</p>
                </div>
              )
            },
            { key: "status", header: "Status", render: (simulation) => <StatusBadge status={simulation.status} /> },
            { key: "scenario", header: "Scenario", render: (simulation) => simulation.scenario_id ?? "None" },
            { key: "updated", header: "Updated", render: (simulation) => formatDateTime(simulation.last_updated) }
          ]}
        />
      ) : (
        <EmptyState
          title="No simulations"
          description="Create a simulation with an existing corpus and corpus index to open the cockpit."
        />
      )}
    </div>
  );
}
