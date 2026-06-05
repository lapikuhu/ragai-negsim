import { useState } from "react";
import { Link } from "react-router-dom";
import { useCreateSessionMutation, useSessionsQuery } from "@/features/sessions/sessionQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { DataTable } from "@/components/common/DataTable";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/api/client";

export function SessionsPage() {
  const query = useSessionsQuery();
  const createMutation = useCreateSessionMutation();
  const [userId, setUserId] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  return (
    <div className="grid gap-6">
      <PageHeader title="User sessions" description="Admin-focused session records from the `/sessions` API." />

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Create session</h2>
        <form
          className="mt-4 grid gap-3 md:grid-cols-3"
          onSubmit={async (event) => {
            event.preventDefault();
            setMessage(null);
            try {
              const session = await createMutation.mutateAsync({
                user_id: userId ? Number(userId) : null,
                expires_at: expiresAt || null
              });
              setMessage(`Created session #${session.id}.`);
            } catch (error) {
              setMessage(getErrorMessage(error));
            }
          }}
        >
          <Field label="User ID">
            <Input value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="Optional" />
          </Field>
          <Field label="Expires at">
            <Input
              type="datetime-local"
              value={expiresAt}
              onChange={(event) => setExpiresAt(event.target.value)}
            />
          </Field>
          <div className="flex items-end">
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating..." : "Create"}
            </Button>
          </div>
        </form>
        {message ? <p className="mt-3 text-sm text-slate-600">{message}</p> : null}
      </Card>

      {query.isLoading ? (
        <LoadingState label="Loading sessions..." />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => query.refetch()} />
      ) : query.data?.length ? (
        <DataTable
          rows={query.data}
          columns={[
            {
              key: "id",
              header: "Session",
              render: (session) => (
                <Link className="font-medium text-accent" to={`/sessions/${session.id}`}>
                  Session #{session.id}
                </Link>
              )
            },
            { key: "user", header: "User ID", render: (session) => session.user_id ?? "Anonymous" },
            { key: "created", header: "Created", render: (session) => formatDateTime(session.created_at) },
            {
              key: "last_seen",
              header: "Last seen",
              render: (session) => formatDateTime(session.last_seen_at ?? session.created_at)
            }
          ]}
        />
      ) : (
        <EmptyState title="No sessions" description="Create a session or wait for login activity to populate this list." />
      )}
    </div>
  );
}
