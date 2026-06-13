import { Link } from "react-router-dom";

import type { SimulationEvaluationListItem } from "@/api/types";
import { DataTable } from "@/components/common/DataTable";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { formatDateTime } from "@/utils/format";

type PaginationProps = {
  hasMore: boolean;
  isBusy?: boolean;
  limit: number;
  skip: number;
  onPageChange: (nextSkip: number) => void;
};

type ReviewsTableProps = PaginationProps & {
  isAdmin: boolean;
  items: SimulationEvaluationListItem[];
  onDelete: (simulationId: number) => Promise<void>;
};

type CompletedTableProps = PaginationProps & {
  currentUserId: number | null;
  isAdmin: boolean;
  items: SimulationEvaluationListItem[];
};

function PaginationControls({ hasMore, isBusy = false, limit, skip, onPageChange }: PaginationProps) {
  return (
    <div className="mt-4 flex items-center justify-end gap-2">
      <Button
        type="button"
        variant="secondary"
        disabled={skip === 0 || isBusy}
        onClick={() => onPageChange(Math.max(0, skip - limit))}
      >
        Previous
      </Button>
      <Button
        type="button"
        variant="secondary"
        disabled={!hasMore || isBusy}
        onClick={() => onPageChange(skip + limit)}
      >
        Next
      </Button>
    </div>
  );
}

export function ReviewsTable({ hasMore, isAdmin, isBusy = false, items, limit, onDelete, onPageChange, skip }: ReviewsTableProps) {
  if (!items.length) {
    return (
      <Card>
        <EmptyState
          title={isAdmin ? "No reviews" : "No reviews yet"}
          description={isAdmin ? "No submitted reviews are available." : "You have not submitted any reviews yet."}
        />
      </Card>
    );
  }

  return (
    <Card>
      <DataTable
        rows={items}
        columns={[
          {
            key: "simulation",
            header: "Simulation",
            render: (item) => (
              <div>
                <div className="font-medium text-slate-900">{item.name}</div>
                <div className="mt-1 text-xs text-slate-500">{item.description ?? "No description"}</div>
              </div>
            )
          },
          {
            key: "scenario",
            header: "Scenario",
            render: (item) => item.scenario_name ?? `Scenario #${item.scenario_id ?? "Unknown"}`
          },
          {
            key: "participant",
            header: "Participant",
            render: (item) => String(item.participant_user_id)
          },
          {
            key: "feedback",
            header: "Review",
            render: (item) => item.teacher_feedback ?? "No feedback"
          },
          {
            key: "reviewedAt",
            header: "Reviewed",
            render: (item) => (item.reviewed_at ? formatDateTime(item.reviewed_at) : "Not reviewed")
          },
          {
            key: "actions",
            header: "Actions",
            render: (item) => (
              <div className="flex items-center gap-2">
                <Link className="text-sm font-medium text-accent" to={`/evaluations/${item.id}/review`}>
                  Edit
                </Link>
                <Button type="button" variant="ghost" onClick={() => void onDelete(item.id)}>
                  Delete
                </Button>
              </div>
            )
          }
        ]}
      />
      <PaginationControls hasMore={hasMore} isBusy={isBusy} limit={limit} skip={skip} onPageChange={onPageChange} />
    </Card>
  );
}

export function CompletedSimulationsTable({
  currentUserId,
  hasMore,
  isAdmin,
  isBusy = false,
  items,
  limit,
  onPageChange,
  skip
}: CompletedTableProps) {
  if (!items.length) {
    return (
      <Card>
        <EmptyState
          title="No completed simulations"
          description="Completed simulations will appear here when they are ready for review."
        />
      </Card>
    );
  }

  return (
    <Card>
      <DataTable
        rows={items}
        columns={[
          {
            key: "simulation",
            header: "Simulation",
            render: (item) => (
              <div>
                <div className="font-medium text-slate-900">{item.name}</div>
                <div className="mt-1 text-xs text-slate-500">{item.description ?? "No description"}</div>
              </div>
            )
          },
          {
            key: "scenario",
            header: "Scenario",
            render: (item) => item.scenario_name ?? `Scenario #${item.scenario_id ?? "Unknown"}`
          },
          {
            key: "participant",
            header: "Participant",
            render: (item) => String(item.participant_user_id)
          },
          {
            key: "updated",
            header: "Last Updated",
            render: (item) => formatDateTime(item.last_updated)
          },
          {
            key: "actions",
            header: "Actions",
            render: (item) => {
              const canEditReview = !item.teacher_reviewed || isAdmin || item.teacher_id === currentUserId;
              return (
                <div className="flex items-center gap-2">
                  <Link className="text-sm font-medium text-accent" to={`/simulations/${item.id}`}>
                    View
                  </Link>
                  {canEditReview ? (
                    <Link className="text-sm font-medium text-accent" to={`/evaluations/${item.id}/review`}>
                      {item.teacher_reviewed ? "Edit" : "Review"}
                    </Link>
                  ) : (
                    <Button type="button" variant="ghost" disabled>
                      Review
                    </Button>
                  )}
                </div>
              );
            }
          }
        ]}
      />
      <PaginationControls hasMore={hasMore} isBusy={isBusy} limit={limit} skip={skip} onPageChange={onPageChange} />
    </Card>
  );
}
