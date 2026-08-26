import { useParams } from "react-router-dom";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { DataTable } from "@/components/common/DataTable";
import { KeyValueList } from "@/components/common/KeyValueList";
import { Card } from "@/components/ui/Card";
import {
  useStudentSimulationsQuery,
  useUserDetailQuery
} from "@/features/users/userQueries";
import { formatDateTime } from "@/utils/format";

export function StudentDetailPage() {
  const username = useParams().username ?? "";
  const userQuery = useUserDetailQuery(username);
  const simulationsQuery = useStudentSimulationsQuery(userQuery.data?.id);

  if (userQuery.isLoading) {
    return <LoadingState label="Loading student..." />;
  }

  if (userQuery.isError || !userQuery.data) {
    return (
      <ErrorState
        message={userQuery.error?.message ?? "Student not found"}
        onRetry={() => userQuery.refetch()}
      />
    );
  }

  const user = userQuery.data;

  return (
    <div className="grid gap-6">
      <PageHeader title={user.username} description="Student account and simulation participation." />

      <Card>
        <KeyValueList
          items={[
            { label: "User ID", value: user.id },
            {
              label: "Email",
              value: user.user_email_address || "Not available"
            },
            {
              label: "Roles",
              value: (user.roles ?? []).map((role) => role.name).join(", ") || "No roles"
            }
          ]}
        />
      </Card>

      <section className="grid gap-3">
        <h2 className="text-lg font-semibold text-slate-950">Simulations</h2>
        {simulationsQuery.isLoading ? (
          <LoadingState label="Loading student simulations..." />
        ) : simulationsQuery.isError ? (
          <ErrorState
            message={simulationsQuery.error.message}
            onRetry={() => simulationsQuery.refetch()}
          />
        ) : simulationsQuery.data?.length ? (
          <DataTable
            rows={simulationsQuery.data}
            columns={[
              { key: "name", header: "Name", render: (simulation) => simulation.name },
              {
                key: "description",
                header: "Description",
                render: (simulation) => simulation.description || "No description"
              },
              { key: "status", header: "Status", render: (simulation) => simulation.status },
              {
                key: "created",
                header: "Created",
                render: (simulation) => formatDateTime(simulation.created_at)
              },
              {
                key: "updated",
                header: "Updated",
                render: (simulation) => formatDateTime(simulation.last_updated)
              }
            ]}
          />
        ) : (
          <EmptyState
            title="No simulations"
            description="This student has not participated in a simulation yet."
          />
        )}
      </section>
    </div>
  );
}
