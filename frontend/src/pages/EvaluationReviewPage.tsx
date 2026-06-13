import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useAuth } from "@/app/AuthProvider";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field, Textarea } from "@/components/ui/Field";
import { useScenarioAuthoringQuery } from "@/features/scenarios/scenarioQueries";
import {
  useReviewSimulationMutation,
  useSimulationDetailQuery,
  useUpdateReviewSimulationMutation
} from "@/features/simulations/simulationQueries";
import { formatDateTime } from "@/utils/format";

export function EvaluationReviewPage() {
  const simulationId = Number(useParams().simulationId);
  const navigate = useNavigate();
  const auth = useAuth();
  const simulationQuery = useSimulationDetailQuery(simulationId);
  const simulation = simulationQuery.data ?? null;
  const scenarioQuery = useScenarioAuthoringQuery(simulation?.scenario_id ?? 0, Boolean(simulation?.scenario_id));
  const createMutation = useReviewSimulationMutation(simulationId);
  const updateMutation = useUpdateReviewSimulationMutation(simulationId);
  const [reviewText, setReviewText] = useState("");

  useEffect(() => {
    if (simulation?.teacher_feedback) {
      setReviewText(simulation.teacher_feedback);
    }
  }, [simulation?.teacher_feedback]);

  if (simulationQuery.isLoading) {
    return <LoadingState label="Loading review context..." />;
  }

  if (simulationQuery.isError || simulation === null) {
    return <ErrorState message={simulationQuery.error?.message ?? "Simulation not found"} onRetry={() => simulationQuery.refetch()} />;
  }

  if (simulation.status !== "completed") {
    return <ErrorState message="Only completed simulations can be reviewed." />;
  }

  const isAdmin = auth.hasRole("admin");
  const isAuthor = simulation.teacher_id === auth.user?.id;
  const canEdit = !simulation.teacher_reviewed || isAdmin || isAuthor;
  const participantUserId = simulation.user_id_participant ?? simulation.user_id_owner;

  if (!canEdit) {
    return <ErrorState message="This review can only be edited by its author or an administrator." />;
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        title={simulation.teacher_reviewed ? "Edit Review" : "Review Simulation"}
        description="Submit teacher feedback for a completed negotiation."
      />
      <Card>
        <div className="grid gap-2 text-sm text-slate-700">
          <div><span className="font-medium text-slate-900">Simulation:</span> {simulation.name}</div>
          <div><span className="font-medium text-slate-900">Scenario:</span> {scenarioQuery.data?.name ?? `Scenario #${simulation.scenario_id ?? "Unknown"}`}</div>
          <div><span className="font-medium text-slate-900">Participant User ID:</span> {participantUserId}</div>
          <div><span className="font-medium text-slate-900">Last Updated:</span> {formatDateTime(simulation.last_updated)}</div>
        </div>
        <form
          className="mt-5 grid gap-4"
          onSubmit={async (event) => {
            event.preventDefault();
            const payload = { teacher_feedback: reviewText };
            if (simulation.teacher_reviewed) {
              await updateMutation.mutateAsync(payload);
            } else {
              await createMutation.mutateAsync(payload);
            }
            navigate("/evaluations");
          }}
        >
          <Field label="Teacher Review">
            <Textarea value={reviewText} onChange={(event) => setReviewText(event.target.value)} />
          </Field>
          <div className="flex items-center gap-3">
            <Button
              type="submit"
              disabled={!reviewText.trim() || createMutation.isPending || updateMutation.isPending}
            >
              Submit
            </Button>
            <Button type="button" variant="secondary" onClick={() => navigate("/evaluations")}>
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
