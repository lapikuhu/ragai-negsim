import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useSimulationsQuery, useCreateSimulationMutation } from "@/features/simulations/simulationQueries";
import { useCorporaQuery } from "@/features/corpora/corpusQueries";
import {
  useCorpusIndicesQuery,
  useChunkingProfilesQuery,
  useVectorStoresQuery
} from "@/features/corpusIndices/corpusIndexQueries";
import { useRagProfilesQuery } from "@/features/ragProfiles/ragProfileQueries";
import { useScenariosQuery } from "@/features/scenarios/scenarioQueries";
import { usePersonasQuery } from "@/features/counterpartPersonas/personaQueries";
import { usePromptsQuery } from "@/features/prompts/promptQueries";
import { useSessionsQuery } from "@/features/sessions/sessionQueries";
import { useUsersQuery } from "@/features/users/userQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { DataTable } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/api/client";

export function SimulationsPage() {
  const query = useSimulationsQuery();
  const corpora = useCorporaQuery();
  const indices = useCorpusIndicesQuery();
  useChunkingProfilesQuery();
  useVectorStoresQuery();
  const ragProfiles = useRagProfilesQuery();
  const scenarios = useScenariosQuery();
  const personas = usePersonasQuery();
  const prompts = usePromptsQuery();
  const sessions = useSessionsQuery();
  const users = useUsersQuery();
  const createMutation = useCreateSimulationMutation();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    name: "",
    description: "",
    corpusId: "",
    corpusIndexId: "",
    ragProfileId: "",
    scenarioId: "",
    personaId: "",
    coachPromptId: "",
    counterpartPromptId: "",
    evaluatorPromptId: "",
    sessionId: "",
    participantId: "",
    userSide: "side_a"
  });
  const [message, setMessage] = useState<string | null>(null);

  const corpusOptions = corpora.data ?? [];
  const ragProfileOptions = ragProfiles.data ?? [];
  const indexOptions = useMemo(
    () => (indices.data ?? []).filter((index) => String(index.corpus_id) === form.corpusId || !form.corpusId),
    [form.corpusId, indices.data]
  );

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
              const simulation = await createMutation.mutateAsync({
                name: form.name,
                description: form.description || null,
                corpus_id: Number(form.corpusId),
                corpus_index_id: Number(form.corpusIndexId),
                rag_profile_id: Number(form.ragProfileId),
                coach_prompt_id: form.coachPromptId ? Number(form.coachPromptId) : null,
                counterpart_prompt_id: form.counterpartPromptId ? Number(form.counterpartPromptId) : null,
                evaluator_prompt_id: form.evaluatorPromptId ? Number(form.evaluatorPromptId) : null,
                session_id: form.sessionId ? Number(form.sessionId) : null,
                user_id_participant: form.participantId ? Number(form.participantId) : null,
                scenario_id: form.scenarioId ? Number(form.scenarioId) : null,
                counter_part_side_persona_id: form.personaId ? Number(form.personaId) : null,
                user_side: form.userSide === "side_b" ? "side_b" : "side_a"
              });
              navigate(`/simulations/${simulation.id}`);
            } catch (error) {
              setMessage(getErrorMessage(error));
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
              onChange={(event) => setForm((current) => ({ ...current, corpusId: event.target.value }))}
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
          <Field label="Corpus index">
            <Select
              value={form.corpusIndexId}
              onChange={(event) => setForm((current) => ({ ...current, corpusIndexId: event.target.value }))}
              required
            >
              <option value="">Select corpus index</option>
              {indexOptions.map((index) => (
                <option key={index.id} value={index.id}>
                  {index.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="RAG profile" hint={ragProfileOptions.length ? "Required" : "Create one from the admin RAG Profiles page first."}>
            <Select
              value={form.ragProfileId}
              onChange={(event) => setForm((current) => ({ ...current, ragProfileId: event.target.value }))}
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

          <Field label="Scenario">
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

          <div className="md:col-span-2 flex items-center gap-3">
            <Button type="submit" disabled={createMutation.isPending || !ragProfileOptions.length}>
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
