import { Link } from "react-router-dom";
import { useDashboardQuery } from "@/features/dashboard/dashboardQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/common/StatusBadge";
import { formatDateTime } from "@/utils/format";

export function DashboardPage() {
  const query = useDashboardQuery();

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
        description="Overview of recent simulations, documents, corpora, users, scenarios, and RAG profiles."
      />

      <div className="grid gap-4 xl:grid-cols-3">
        <Card>
          <DashboardCardHeader label="Recent simulations" to="/simulations" />
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
          <DashboardCardHeader label="Recent documents" to="/documents" />
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
          <DashboardCardHeader label="Recent corpora" to="/corpora" />
          <div className="mt-4 grid gap-3">
            {data.corpora.length ? (
              data.corpora.map((corpus) => (
                <Link key={corpus.id} className="rounded-xl bg-slate-50 p-3" to={`/corpora/${corpus.id}`}>
                  <strong className="text-sm">{corpus.name}</strong>
                  <p className="mt-2 text-xs text-slate-500">
                    Created {formatDateTime(corpus.created_at)}
                    {corpus.created_by_username ? ` by ${corpus.created_by_username}` : ""}
                  </p>
                </Link>
              ))
            ) : (
              <p className="text-sm text-slate-600">No corpora yet.</p>
            )}
          </div>
        </Card>

        <Card>
          <DashboardCardHeader label="Users" to="/users" />
          <div className="mt-4 grid gap-3">
            {data.users.length ? (
              data.users.map((user) => (
                <div key={user.id} className="rounded-xl bg-slate-50 p-3">
                  <strong className="text-sm">{user.username}</strong>
                  <p className="mt-2 text-xs text-slate-500">
                    {user.roles?.length ? user.roles.map((role) => role.name).join(", ") : "No roles assigned"}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-600">No users visible.</p>
            )}
          </div>
        </Card>

        <Card>
          <DashboardCardHeader label="Recent scenarios" to="/scenarios" />
          <div className="mt-4 grid gap-3">
            {data.scenarios.length ? (
              data.scenarios.map((scenario) => (
                <Link key={scenario.id} className="rounded-xl bg-slate-50 p-3" to={`/scenarios/${scenario.id}`}>
                  <strong className="text-sm">{scenario.name}</strong>
                  <p className="mt-2 text-xs text-slate-500">
                    Updated {formatDateTime(scenario.last_updated)}
                    {scenario.simulation_ids?.length ? ` - ${scenario.simulation_ids.length} simulations` : ""}
                  </p>
                </Link>
              ))
            ) : (
              <p className="text-sm text-slate-600">No scenarios yet.</p>
            )}
          </div>
        </Card>

        <Card>
          <DashboardCardHeader label="Recent RAG profiles" to="/rag-profiles" />
          <div className="mt-4 grid gap-3">
            {data.ragProfiles.length ? (
              data.ragProfiles.map((profile) => (
                <Link key={profile.id} className="rounded-xl bg-slate-50 p-3" to="/rag-profiles">
                  <div className="flex items-center justify-between gap-3">
                    <strong className="text-sm">{profile.name}</strong>
                    <StatusBadge status={profile.strategy} />
                  </div>
                  <p className="mt-2 text-xs text-slate-500">Updated {formatDateTime(profile.last_updated)}</p>
                </Link>
              ))
            ) : (
              <p className="text-sm text-slate-600">No RAG profiles yet.</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function DashboardCardHeader({ label, to }: { label: string; to: string }) {
  return (
    <h2 className="text-lg font-semibold text-slate-950">
      <Link className="text-slate-950 transition hover:text-accent" to={to}>
        {label}
      </Link>
    </h2>
  );
}
