import { Link } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/common/StatusBadge";
import { formatDateTime } from "@/utils/format";
import type { SimulationRead } from "@/api/types";

export function EvaluationSummaryList({ simulations }: { simulations: SimulationRead[] }) {
  if (!simulations.length) {
    return (
      <Card>
        <p className="text-sm text-slate-600">
          No standalone evaluations are exposed by the current API. This view surfaces teacher review and status fields
          from simulations instead.
        </p>
      </Card>
    );
  }

  return (
    <div className="grid gap-4">
      {simulations.map((simulation) => (
        <Card key={simulation.id}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold text-slate-900">{simulation.name}</h3>
              <p className="mt-1 text-sm text-slate-600">
                Review status: {simulation.teacher_reviewed ? "Reviewed" : "Pending"} · Updated{" "}
                {formatDateTime(simulation.last_updated)}
              </p>
            </div>
            <StatusBadge status={simulation.status} />
          </div>
          <p className="mt-3 text-sm text-slate-700">{simulation.teacher_feedback ?? "No teacher feedback recorded yet."}</p>
          <div className="mt-4">
            <Link className="text-sm font-medium text-accent" to={`/simulations/${simulation.id}`}>
              Open simulation cockpit
            </Link>
          </div>
        </Card>
      ))}
    </div>
  );
}
