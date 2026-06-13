import { useState } from "react";

import { useAuth } from "@/app/AuthProvider";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import {
  CompletedSimulationsTable,
  ReviewsTable
} from "@/features/evaluations/evaluationViews";
import {
  useCompletedSimulationsQuery,
  useDeleteReviewSimulationMutation,
  useReviewedSimulationsQuery
} from "@/features/simulations/simulationQueries";

export function EvaluationsPage() {
  const auth = useAuth();
  const isAdmin = auth.hasRole("admin");
  const [reviewSkip, setReviewSkip] = useState(0);
  const [completedSkip, setCompletedSkip] = useState(0);
  const limit = 20;
  const reviewsQuery = useReviewedSimulationsQuery(reviewSkip, limit);
  const completedQuery = useCompletedSimulationsQuery(completedSkip, limit);
  const deleteMutation = useDeleteReviewSimulationMutation();

  if (reviewsQuery.isLoading || completedQuery.isLoading) {
    return <LoadingState label="Loading evaluation data..." />;
  }

  if (reviewsQuery.isError) {
    return <ErrorState message={reviewsQuery.error.message} onRetry={() => reviewsQuery.refetch()} />;
  }

  if (completedQuery.isError) {
    return <ErrorState message={completedQuery.error.message} onRetry={() => completedQuery.refetch()} />;
  }

  return (
    <div className="grid gap-6">
      <PageHeader title="Evaluations" description="Review completed simulations and manage teacher feedback." />
      <section className="grid gap-3">
        <h2 className="text-lg font-semibold text-slate-950">{isAdmin ? "All Reviews" : "My Reviews"}</h2>
        <ReviewsTable
          isAdmin={isAdmin}
          items={reviewsQuery.data?.items ?? []}
          skip={reviewSkip}
          limit={reviewsQuery.data?.limit ?? limit}
          hasMore={reviewsQuery.data?.has_more ?? false}
          isBusy={deleteMutation.isPending}
          onPageChange={setReviewSkip}
          onDelete={async (simulationId) => {
            if (!window.confirm("Delete this review?")) {
              return;
            }
            await deleteMutation.mutateAsync(simulationId);
            const nextReviewItems = reviewsQuery.data?.items.length ?? 0;
            if (reviewSkip > 0 && nextReviewItems === 1) {
              setReviewSkip((current) => Math.max(0, current - limit));
            }
          }}
        />
      </section>
      <section className="grid gap-3">
        <h2 className="text-lg font-semibold text-slate-950">Completed Simulations</h2>
        <CompletedSimulationsTable
          currentUserId={auth.user?.id ?? null}
          isAdmin={isAdmin}
          items={completedQuery.data?.items ?? []}
          skip={completedSkip}
          limit={completedQuery.data?.limit ?? limit}
          hasMore={completedQuery.data?.has_more ?? false}
          onPageChange={setCompletedSkip}
        />
      </section>
    </div>
  );
}
