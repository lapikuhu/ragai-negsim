import { Link } from "react-router-dom";
import { useDashboardQuery } from "@/features/dashboard/dashboardQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/Button";
import { formatDateTime } from "@/utils/format";
import { useAuth } from "@/app/AuthProvider";

export function DashboardPage() {
  const query = useDashboardQuery();
  const auth = useAuth();

  if (query.isLoading) {
    return <LoadingState label="Loading dashboard..." />;
  }

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => query.refetch()} />;
  }

  const data = query.data;
  if (!data) {
    return <EmptyState title="No dashboard data" description="The backend did not return any dashboard-ready data." />;
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Dashboard"
        description="Overview of recent simulations, documents, and admin session activity."
        actions={
          <>
            <Link to="/simulations">
              <Button type="button">Start simulation</Button>
            </Link>
            <Link to="/documents">
              <Button type="button" variant="secondary">
                Upload document
              </Button>
            </Link>
          </>
        }
      />

      <div className="grid gap-4 xl:grid-cols-3">
        <Card>
          <h2 className="text-lg font-semibold text-slate-950">Recent simulations</h2>
          <div className="mt-4 grid gap-3">
            {data.simulations.length ? (
              data.simulations.map((simulation) => (
                <Link key={simulation.id} className="rounded-xl bg-slate-50 p-3" to={`/simulations/${simulation.id}`}>
                  <div className="flex items-center justify-between gap-3">
                    <strong className="text-sm">{simulation.name}</strong>
                    <StatusBadge status={simulation.status} />
                  </div>
                  <p className="mt-2 text-xs text-slate-500">{formatDateTime(simulation.last_updated)}</p>
                </Link>
              ))
            ) : (
              <p className="text-sm text-slate-600">No simulations yet.</p>
            )}
          </div>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold text-slate-950">Recent documents</h2>
          <div className="mt-4 grid gap-3">
            {data.documents.length ? (
              data.documents.map((document) => (
                <Link key={document.id} className="rounded-xl bg-slate-50 p-3" to={`/documents/${document.id}`}>
                  <strong className="text-sm">{document.name}</strong>
                  <p className="mt-2 text-xs text-slate-500">Uploaded {formatDateTime(document.uploaded_at)}</p>
                </Link>
              ))
            ) : (
              <p className="text-sm text-slate-600">No raw documents uploaded yet.</p>
            )}
          </div>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold text-slate-950">Admin session activity</h2>
          <div className="mt-4 grid gap-3">
            {auth.hasRole("admin") ? (
              data.sessions.length ? (
                data.sessions.map((session) => (
                  <Link key={session.id} className="rounded-xl bg-slate-50 p-3" to={`/sessions/${session.id}`}>
                    <strong className="text-sm">Session #{session.id}</strong>
                    <p className="mt-2 text-xs text-slate-500">
                      Last seen {formatDateTime(session.last_seen_at ?? session.created_at)}
                    </p>
                  </Link>
                ))
              ) : (
                <p className="text-sm text-slate-600">No admin-visible session activity yet.</p>
              )
            ) : (
              <p className="text-sm text-slate-600">Session management is only exposed to admins by the backend.</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
