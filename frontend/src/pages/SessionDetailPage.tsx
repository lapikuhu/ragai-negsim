import { useParams } from "react-router-dom";
import {
  useEndSessionMutation,
  useHeartbeatSessionMutation,
  useSessionDetailQuery
} from "@/features/sessions/sessionQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { KeyValueList } from "@/components/common/KeyValueList";
import { formatDateTime } from "@/utils/format";

export function SessionDetailPage() {
  const sessionId = Number(useParams().sessionId);
  const query = useSessionDetailQuery(sessionId);
  const heartbeatMutation = useHeartbeatSessionMutation(sessionId);
  const endMutation = useEndSessionMutation(sessionId);

  if (query.isLoading) {
    return <LoadingState label="Loading session..." />;
  }

  if (query.isError || !query.data) {
    return <ErrorState message={query.error?.message ?? "Session not found"} onRetry={() => query.refetch()} />;
  }

  const session = query.data;

  return (
    <div className="grid gap-6">
      <PageHeader
        title={`Session #${session.id}`}
        description="Admin detail view for a login session record."
        actions={
          <>
            <Button
              type="button"
              variant="secondary"
              disabled={heartbeatMutation.isPending}
              onClick={() => heartbeatMutation.mutate({ last_seen_at: new Date().toISOString() })}
            >
              Heartbeat
            </Button>
            <Button
              type="button"
              variant="danger"
              disabled={endMutation.isPending}
              onClick={() => endMutation.mutate({ ended_at: new Date().toISOString() })}
            >
              End session
            </Button>
          </>
        }
      />

      <Card>
        <KeyValueList
          items={[
            { label: "User ID", value: session.user_id ?? "Anonymous" },
            { label: "Created", value: formatDateTime(session.created_at) },
            { label: "Expires", value: formatDateTime(session.expires_at) },
            { label: "Last seen", value: formatDateTime(session.last_seen_at) },
            { label: "Ended", value: formatDateTime(session.ended_at) }
          ]}
        />
      </Card>
    </div>
  );
}
