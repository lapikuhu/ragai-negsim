import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import type {
  CounterpartPersonaRead,
  SimulationReadWithState,
  SimulationTokenUsage,
  SimulationProxyTurnResponse,
  SimulationTurnResponse
} from "@/api/types";
import {
  useDisableSimulationProxyMutation,
  useSimulationDetailQuery,
  useSimulationProxyTurnMutation,
  useSimulationTurnMutation,
  useStartSimulationMutation
} from "@/features/simulations/simulationQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { SimulationTranscript } from "@/features/simulations/SimulationTranscript";
import { SimulationInput } from "@/features/simulations/SimulationInput";
import { SimulationInspector } from "@/features/simulations/SimulationInspector";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { usePersonasQuery } from "@/features/counterpartPersonas/personaQueries";

function hasVisibleEvaluation(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && Object.keys(value as Record<string, unknown>).length > 0;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}

function getTokenUsage(
  simulation: SimulationReadWithState | null,
  latestTurn: SimulationTurnResponse | SimulationProxyTurnResponse | null
): SimulationTokenUsage | null {
  if (latestTurn?.token_usage) {
    return latestTurn.token_usage;
  }

  const persisted = simulation?.negotiation_state?.data?.token_usage;
  return isRecord(persisted) ? (persisted as SimulationTokenUsage) : null;
}

export function SimulationCockpitPage() {
  const simulationId = Number(useParams().simulationId);
  const query = useSimulationDetailQuery(simulationId);
  const personasQuery = usePersonasQuery();
  const startMutation = useStartSimulationMutation(simulationId);
  const turnMutation = useSimulationTurnMutation(simulationId);
  const proxyTurnMutation = useSimulationProxyTurnMutation(simulationId);
  const disableProxyMutation = useDisableSimulationProxyMutation(simulationId);
  const [maxTurnCount, setMaxTurnCount] = useState("12");
  const [latestTurn, setLatestTurn] = useState<SimulationTurnResponse | SimulationProxyTurnResponse | null>(null);
  const [isEvaluationVisible, setIsEvaluationVisible] = useState(false);
  const [proxyOverride, setProxyOverride] = useState<{ active: boolean; personaId: number | null; personaName: string | null } | null>(null);
  const simulation = query.data ?? null;
  const effectiveStatus = latestTurn?.status ?? simulation?.status ?? "created";
  const effectivePhase = latestTurn?.phase ?? simulation?.negotiation_state?.current_phase ?? null;
  const isTerminal = effectiveStatus === "completed" || effectivePhase === "ended";
  const canStart = simulation?.status === "created";
  const persistedProxyPersona = isRecord(simulation?.negotiation_state?.data?.user_proxy_persona)
    ? simulation.negotiation_state.data.user_proxy_persona
    : null;
  const persistedProxyActive = simulation?.negotiation_state?.data?.auto_user_proxy_enabled === true;
  const effectiveProxyState = proxyOverride ?? {
    active: persistedProxyActive,
    personaId:
      typeof persistedProxyPersona?.id === "number"
        ? persistedProxyPersona.id
        : null,
    personaName:
      typeof persistedProxyPersona?.name === "string"
        ? persistedProxyPersona.name
        : null
  };
  const canSendTurn = ["active", "paused"].includes(effectiveStatus) && !isTerminal && !effectiveProxyState.active;
  const persistedEvaluation = simulation?.negotiation_state?.data?.final_evaluation;
  const currentEvaluation = hasVisibleEvaluation(latestTurn?.final_evaluation)
    ? latestTurn.final_evaluation
    : hasVisibleEvaluation(persistedEvaluation)
      ? persistedEvaluation
      : null;
  const canEvaluate = isTerminal && Boolean(currentEvaluation) && !isEvaluationVisible;
  const evaluationUnavailableMessage =
    isTerminal && !currentEvaluation
      ? "Final evaluation is not available for this completed simulation."
      : null;
  const tokenUsage = getTokenUsage(simulation, latestTurn);
  const proxyActiveLabel = effectiveProxyState.active
    ? `Proxy active: ${effectiveProxyState.personaName ?? "Neutral"}`
    : null;

  useEffect(() => {
    if (
      query.isLoading ||
      query.isError ||
      simulation === null ||
      !effectiveProxyState.active ||
      isTerminal ||
      proxyTurnMutation.isPending ||
      !simulationId
    ) {
      return;
    }
    void proxyTurnMutation
      .mutateAsync({
        persona_id: effectiveProxyState.personaId,
        duration: "remainder"
      })
      .then((result) => {
        setLatestTurn(result);
        setProxyOverride({
          active: result.auto_user_proxy_enabled,
          personaId:
            typeof result.user_proxy_persona?.id === "number"
              ? result.user_proxy_persona.id
              : null,
          personaName:
            typeof result.user_proxy_persona?.name === "string"
              ? result.user_proxy_persona.name
              : null
        });
      })
      .catch(() => undefined);
  }, [
    effectiveProxyState.active,
    effectiveProxyState.personaId,
    isTerminal,
    proxyTurnMutation,
    query.isError,
    query.isLoading,
    simulation,
    simulationId
  ]);

  if (query.isLoading) {
    return <LoadingState label="Loading simulation..." />;
  }

  if (query.isError || simulation === null) {
    return <ErrorState message={query.error?.message ?? "Simulation not found"} onRetry={() => query.refetch()} />;
  }

  const transcriptSimulation =
    latestTurn === null
      ? simulation
      : {
          ...simulation,
          messages: latestTurn.messages
        };

  return (
    <div className="grid gap-6">
      <PageHeader
        title={simulation.name}
        description={simulation.description ?? "Simulation-backed negotiation cockpit."}
        actions={
          <div className="flex items-center gap-2">
            {typeof tokenUsage?.simulation_total === "number" ? (
              <span className="text-sm font-medium text-slate-600">
                Simulation Total Tokens: {tokenUsage.simulation_total}
              </span>
            ) : null}
            <StatusBadge status={effectiveStatus} />
          </div>
        }
      />

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(360px,520px)]">
        <div className="grid content-start gap-4">
          {canStart ? (
            <Card>
              <h2 className="text-lg font-semibold text-slate-950">Start simulation</h2>
              <form
                className="mt-4 grid gap-3"
                onSubmit={async (event) => {
                  event.preventDefault();
                  await startMutation.mutateAsync({
                    side_a: {},
                    side_b: {},
                    max_turn_count: Number(maxTurnCount || "12")
                  });
                }}
              >
                <Field label="Max turn count">
                  <Input value={maxTurnCount} onChange={(event) => setMaxTurnCount(event.target.value)} />
                </Field>
                <div>
                  <Button type="submit" disabled={startMutation.isPending}>
                    {startMutation.isPending ? "Starting..." : "Start simulation"}
                  </Button>
                </div>
              </form>
            </Card>
          ) : null}
          <SimulationTranscript simulation={transcriptSimulation} />
          <SimulationInput
            disabled={!["active", "paused"].includes(effectiveStatus) || isTerminal || turnMutation.isPending}
            disabledMessage={
              isTerminal ? "This simulation has ended. No further turns can be sent." : null
            }
            onProxySubmit={async ({ personaId, duration }) => {
              const result = await proxyTurnMutation.mutateAsync({
                persona_id: personaId,
                duration
              });
              setLatestTurn(result);
              setProxyOverride({
                active: result.auto_user_proxy_enabled,
                personaId:
                  typeof result.user_proxy_persona?.id === "number"
                    ? result.user_proxy_persona.id
                    : null,
                personaName:
                  typeof result.user_proxy_persona?.name === "string"
                    ? result.user_proxy_persona.name
                    : null
              });
            }}
            proxyPersonaOptions={(personasQuery.data ?? []).map((persona: CounterpartPersonaRead) => ({
              id: persona.id,
              name: persona.name
            }))}
            isProxyActive={effectiveProxyState.active}
            proxyActiveLabel={proxyActiveLabel}
            onTakeControl={async () => {
              await disableProxyMutation.mutateAsync();
              setProxyOverride({ active: false, personaId: null, personaName: null });
            }}
            proxyBusy={proxyTurnMutation.isPending || disableProxyMutation.isPending}
            canEvaluate={canEvaluate}
            evaluation={currentEvaluation}
            evaluatorTotalTokens={tokenUsage?.evaluator_total ?? null}
            isEvaluationVisible={isEvaluationVisible}
            evaluationUnavailableMessage={evaluationUnavailableMessage}
            onEvaluate={() => {
              if (currentEvaluation) {
                setIsEvaluationVisible(true);
              }
            }}
            onSubmit={async (message) => {
              setProxyOverride({ active: false, personaId: null, personaName: null });
              const result = await turnMutation.mutateAsync({ message, current_offer: null });
              setLatestTurn(result);
            }}
          />
        </div>

        <SimulationInspector simulation={simulation} latestTurn={latestTurn ?? null} />
      </div>
    </div>
  );
}
