import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import type {
  CounterpartPersonaRead,
  RagProfileRead,
  ScenarioPublicRead,
  SimulationRead,
  UserRead
} from "@/api/types";
import { DataTable } from "@/components/common/DataTable";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { KeyValueList } from "@/components/common/KeyValueList";
import { LoadingState } from "@/components/common/LoadingState";
import { PageHeader } from "@/components/common/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import {
  useUserSimulationsQuery,
  useUserCorporaQuery,
  useUserDetailQuery,
  useUserEvaluationsQuery,
  useUserPersonasQuery,
  useUserRagProfilesQuery,
  useUserScenariosQuery,
  useUsersCreatedByQuery
} from "@/features/users/userQueries";
import type { UserActivityPage } from "@/features/users/userQueries";
import { formatDateTime } from "@/utils/format";

type ActivityQuery<T> = {
  data?: UserActivityPage<T>;
  error: Error | null;
  isError: boolean;
  isLoading: boolean;
  refetch: () => unknown;
};

type ActivityColumn<T> = {
  key: string;
  header: string;
  render: (item: T) => ReactNode;
};

const activityLinkClass = "font-medium text-blue-700 hover:text-blue-900 hover:underline";

function ActivityCard<T extends { id?: number | string }>({
  title,
  query,
  columns,
  emptyDescription,
  emptyTitle,
  page,
  onPageChange
}: {
  title: string;
  query: ActivityQuery<T>;
  columns: ActivityColumn<T>[];
  emptyDescription: string;
  emptyTitle?: string;
  page: number;
  onPageChange: (page: number) => void;
}) {
  return (
    <Card className="grid gap-3">
      <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
      {query.isLoading ? (
        <LoadingState label={`Loading ${title.toLowerCase()}...`} />
      ) : query.isError ? (
        <ErrorState
          message={query.error?.message ?? `Unable to load ${title.toLowerCase()}`}
          onRetry={() => query.refetch()}
        />
      ) : query.data?.items.length ? (
        <DataTable rows={query.data.items} columns={columns} />
      ) : (
        <EmptyState title={emptyTitle ?? `No ${title.toLowerCase()}`} description={emptyDescription} />
      )}
      {query.data && (page > 1 || query.data.hasMore) ? (
        <div className="flex items-center justify-end gap-3">
          <Button
            type="button"
            variant="secondary"
            disabled={page === 1}
            aria-label={`Previous ${title.toLowerCase()} page`}
            onClick={() => onPageChange(page - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-slate-600">Page {page}</span>
          <Button
            type="button"
            variant="secondary"
            disabled={!query.data.hasMore}
            aria-label={`Next ${title.toLowerCase()} page`}
            onClick={() => onPageChange(page + 1)}
          >
            Next
          </Button>
        </div>
      ) : null}
    </Card>
  );
}

const simulationColumns: ActivityColumn<SimulationRead>[] = [
  {
    key: "name",
    header: "Name",
    render: (simulation) => (
      <Link className={activityLinkClass} to={`/simulations/${simulation.id}`}>
        {simulation.name}
      </Link>
    )
  },
  { key: "description", header: "Description", render: (item) => item.description || "No description" },
  { key: "status", header: "Status", render: (item) => item.status },
  { key: "created", header: "Created", render: (item) => formatDateTime(item.created_at) },
  { key: "updated", header: "Updated", render: (item) => formatDateTime(item.last_updated) }
];

const evaluationColumns: ActivityColumn<SimulationRead>[] = [
  {
    key: "name",
    header: "Simulation",
    render: (simulation) => (
      <Link className={activityLinkClass} to={`/evaluations/${simulation.id}/review`}>
        {simulation.name}
      </Link>
    )
  },
  { key: "status", header: "Status", render: (item) => item.status },
  { key: "updated", header: "Reviewed", render: (item) => formatDateTime(item.last_updated) }
];

const scenarioColumns: ActivityColumn<ScenarioPublicRead>[] = [
  { key: "name", header: "Title", render: (scenario) => scenario.name }
];

const personaColumns: ActivityColumn<CounterpartPersonaRead>[] = [
  { key: "name", header: "Title", render: (persona) => persona.name }
];

type ActivityKey = "simulations" | "evaluations" | "scenarios" | "corpora" | "personas" | "ragProfiles" | "users";
const ACTIVITY_PAGE_SIZE = 20;

export function UserDetailPage() {
  const username = useParams().username ?? "";
  return <UserDetailContent key={username} username={username} />;
}

function UserDetailContent({ username }: { username: string }) {
  const userQuery = useUserDetailQuery(username);
  const roles = new Set(userQuery.data?.roles?.map((role) => role.name) ?? []);
  const isAdmin = roles.has("admin");
  const isTeacherOrAdmin = isAdmin || roles.has("teacher");
  const userId = userQuery.data?.id;
  const [activityPages, setActivityPages] = useState<Record<ActivityKey, number>>({
    simulations: 1,
    evaluations: 1,
    scenarios: 1,
    corpora: 1,
    personas: 1,
    ragProfiles: 1,
    users: 1
  });
  const activitySkip = (key: ActivityKey) => (activityPages[key] - 1) * ACTIVITY_PAGE_SIZE;
  const setActivityPage = (key: ActivityKey, page: number) => {
    setActivityPages((current) => ({ ...current, [key]: Math.max(1, page) }));
  };

  const simulationsQuery = useUserSimulationsQuery(userId, true, activitySkip("simulations"), ACTIVITY_PAGE_SIZE);
  const evaluationsQuery = useUserEvaluationsQuery(userId, isTeacherOrAdmin, activitySkip("evaluations"), ACTIVITY_PAGE_SIZE);
  const scenariosQuery = useUserScenariosQuery(userId, isTeacherOrAdmin, activitySkip("scenarios"), ACTIVITY_PAGE_SIZE);
  const corporaQuery = useUserCorporaQuery(userId, isTeacherOrAdmin, activitySkip("corpora"), ACTIVITY_PAGE_SIZE);
  const personasQuery = useUserPersonasQuery(userId, isTeacherOrAdmin, activitySkip("personas"), ACTIVITY_PAGE_SIZE);
  const ragProfilesQuery = useUserRagProfilesQuery(userId, isAdmin, activitySkip("ragProfiles"), ACTIVITY_PAGE_SIZE);
  const createdUsersQuery = useUsersCreatedByQuery(userId, isAdmin, activitySkip("users"), ACTIVITY_PAGE_SIZE);

  if (userQuery.isLoading) {
    return <LoadingState label="Loading user..." />;
  }

  if (userQuery.isError || !userQuery.data) {
    return (
      <ErrorState
        message={userQuery.error?.message ?? "User not found"}
        onRetry={() => userQuery.refetch()}
      />
    );
  }

  const user = userQuery.data;

  return (
    <div className="grid gap-6">
      <PageHeader title={user.username} description="User account and activity." />

      <Card>
        <KeyValueList
          items={[
            { label: "User ID", value: user.id },
            { label: "Email", value: user.user_email_address || "Not available" },
            {
              label: "Roles",
              value: (user.roles ?? []).map((role) => role.name).join(", ") || "No roles"
            }
          ]}
        />
      </Card>

      {isTeacherOrAdmin ? (
        <ActivityCard
          title="Evaluations given"
          query={evaluationsQuery}
          columns={evaluationColumns}
          emptyDescription="This user has not submitted an evaluation yet."
          page={activityPages.evaluations}
          onPageChange={(page) => setActivityPage("evaluations", page)}
        />
      ) : null}

      <ActivityCard
        title="Simulations participated in"
        query={simulationsQuery}
        columns={simulationColumns}
        emptyTitle="No simulations"
        emptyDescription="This user has not participated in a simulation yet."
        page={activityPages.simulations}
        onPageChange={(page) => setActivityPage("simulations", page)}
      />

      {isTeacherOrAdmin ? (
        <>
          <ActivityCard
            title="Scenarios created"
            query={scenariosQuery}
            columns={scenarioColumns}
            emptyDescription="This user has not created a scenario yet."
            page={activityPages.scenarios}
            onPageChange={(page) => setActivityPage("scenarios", page)}
          />
          <ActivityCard
            title="Corpora created"
            query={corporaQuery}
            columns={[
              {
                key: "name",
                header: "Name",
                render: (corpus) => (
                  <Link className={activityLinkClass} to={`/corpora/${corpus.id}`}>
                    {corpus.name}
                  </Link>
                )
              },
              { key: "description", header: "Description", render: (corpus) => corpus.description || "No description" }
            ]}
            emptyDescription="This user has not created a corpus yet."
            page={activityPages.corpora}
            onPageChange={(page) => setActivityPage("corpora", page)}
          />
          <ActivityCard
            title="Personas created"
            query={personasQuery}
            columns={personaColumns}
            emptyDescription="This user has not created a persona yet."
            page={activityPages.personas}
            onPageChange={(page) => setActivityPage("personas", page)}
          />
        </>
      ) : null}

      {isAdmin ? (
        <>
          <ActivityCard
            title="RAG Profiles created"
            query={ragProfilesQuery}
            columns={[
              { key: "name", header: "Name", render: (profile: RagProfileRead) => profile.name },
              { key: "strategy", header: "Strategy", render: (profile: RagProfileRead) => profile.strategy }
            ]}
            emptyDescription="This user has not created a RAG profile yet."
            page={activityPages.ragProfiles}
            onPageChange={(page) => setActivityPage("ragProfiles", page)}
          />
          <ActivityCard
            title="Users created"
            query={createdUsersQuery}
            columns={[
              {
                key: "username",
                header: "Username",
                render: (createdUser: UserRead) => (
                  <Link className={activityLinkClass} to={`/users/${createdUser.username}`}>
                    {createdUser.username}
                  </Link>
                )
              },
              {
                key: "roles",
                header: "Roles",
                render: (createdUser: UserRead) =>
                  (createdUser.roles ?? []).map((role) => role.name).join(", ") || "No roles"
              }
            ]}
            emptyDescription="This admin has not created a user yet."
            page={activityPages.users}
            onPageChange={(page) => setActivityPage("users", page)}
          />
        </>
      ) : null}
    </div>
  );
}
