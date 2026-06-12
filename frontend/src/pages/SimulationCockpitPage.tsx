import { useState } from "react";
import { useParams } from "react-router-dom";
import type { SimulationTurnResponse } from "@/api/types";
import {
  useReviewSimulationMutation,
  useSimulationDetailQuery,
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
import { Field, Input, Textarea } from "@/components/ui/Field";
import { useAuth } from "@/app/AuthProvider";

function hasVisibleEvaluation(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && Object.keys(value as Record<string, unknown>).length > 0;
}

export function SimulationCockpitPage() {
  const simulationId = Number(useParams().simulationId);
  const auth = useAuth();
  const query = useSimulationDetailQuery(simulationId);
  const startMutation = useStartSimulationMutation(simulationId);
  const turnMutation = useSimulationTurnMutation(simulationId);
  const reviewMutation = useReviewSimulationMutation(simulationId);
  const [maxTurnCount, setMaxTurnCount] = useState("12");
  const [reviewText, setReviewText] = useState("");
  const [latestTurn, setLatestTurn] = useState<SimulationTurnResponse | null>(null);
  const [isEvaluationVisible, setIsEvaluationVisible] = useState(false);

  if (query.isLoading) {
    return <LoadingState label="Loading simulation..." />;
  }

  if (query.isError || !query.data) {
    return <ErrorState message={query.error?.message ?? "Simulation not found"} onRetry={() => query.refetch()} />;
  }

  const simulation = query.data;
  const effectiveStatus = latestTurn?.status ?? simulation.status;
  const effectivePhase = latestTurn?.phase ?? simulation.negotiation_state?.current_phase ?? null;
  const isTerminal = effectiveStatus === "completed" || effectivePhase === "ended";
  const canStart = simulation.status === "created";
  const canSendTurn = ["active", "paused"].includes(effectiveStatus) && !isTerminal;
  const canReview = auth.hasRole("teacher");
  const persistedEvaluation = simulation.negotiation_state?.data?.final_evaluation;
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

  return (
    <div className="grid gap-6">
      <PageHeader
        title={simulation.name}
        description={simulation.description ?? "Simulation-backed negotiation cockpit."}
        actions={
          <div className="flex items-center gap-2">
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
          <SimulationTranscript simulation={simulation} />
          <SimulationInput
            disabled={!canSendTurn || turnMutation.isPending}
            disabledMessage={
              isTerminal ? "This simulation has ended. No further turns can be sent." : null
            }
            canEvaluate={canEvaluate}
            evaluation={currentEvaluation}
            isEvaluationVisible={isEvaluationVisible}
            evaluationUnavailableMessage={evaluationUnavailableMessage}
            onEvaluate={() => {
              if (currentEvaluation) {
                setIsEvaluationVisible(true);
              }
            }}
            onSubmit={async (message) => {
              const result = await turnMutation.mutateAsync({ message, current_offer: null });
              setLatestTurn(result);
            }}
          />

          {canReview ? (
            <Card>
              <h2 className="text-lg font-semibold text-slate-950">Teacher review</h2>
              <form
                className="mt-4 grid gap-3"
                onSubmit={async (event) => {
                  event.preventDefault();
                  await reviewMutation.mutateAsync({ teacher_feedback: reviewText });
                  setReviewText("");
                }}
              >
                <Field label="Feedback">
                  <Textarea value={reviewText} onChange={(event) => setReviewText(event.target.value)} />
                </Field>
                <div>
                  <Button type="submit" disabled={reviewMutation.isPending || !reviewText.trim()}>
                    {reviewMutation.isPending ? "Submitting..." : "Submit review"}
                  </Button>
                </div>
              </form>
            </Card>
          ) : null}
        </div>

        <SimulationInspector simulation={simulation} latestTurn={latestTurn ?? null} />
      </div>
    </div>
  );
}
