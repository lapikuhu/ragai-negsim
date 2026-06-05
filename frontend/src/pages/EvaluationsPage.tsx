import { useSimulationsQuery } from "@/features/simulations/simulationQueries";
import { EvaluationSummaryList } from "@/features/evaluations/evaluationViews";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";

export function EvaluationsPage() {
  const query = useSimulationsQuery();

  if (query.isLoading) {
    return <LoadingState label="Loading evaluation data..." />;
  }

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => query.refetch()} />;
  }

  const reviewLikeItems = (query.data ?? []).filter((simulation) => simulation.teacher_reviewed || simulation.teacher_feedback);

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Evaluations"
        description="This backend does not expose a standalone evaluations API, so this screen derives read-only evaluation signals from simulations."
      />
      <EvaluationSummaryList simulations={reviewLikeItems} />
    </div>
  );
}
