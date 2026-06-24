import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SessionDetailPage } from "./SessionDetailPage";

const state = vi.hoisted(() => ({
  sessionQuery: {
    isLoading: false,
    isError: false,
    data: {
      id: 7,
      user_id: 12,
      created_at: "2026-06-24T10:00:00Z",
      expires_at: null,
      last_seen_at: "2026-06-24T10:05:00Z",
      ended_at: null
    },
    error: null as Error | null,
    refetch: vi.fn()
  },
  heartbeatMutation: {
    isPending: false,
    isError: false,
    error: null as Error | null,
    mutate: vi.fn()
  },
  endMutation: {
    isPending: false,
    isError: false,
    error: null as Error | null,
    mutate: vi.fn()
  }
}));

vi.mock("react-router-dom", () => ({
  useParams: () => ({ sessionId: "7" })
}));

vi.mock("@/features/sessions/sessionQueries", () => ({
  useSessionDetailQuery: () => state.sessionQuery,
  useHeartbeatSessionMutation: () => state.heartbeatMutation,
  useEndSessionMutation: () => state.endMutation
}));

describe("SessionDetailPage", () => {
  beforeEach(() => {
    state.sessionQuery.isLoading = false;
    state.sessionQuery.isError = false;
    state.sessionQuery.error = null;
    state.sessionQuery.data = {
      id: 7,
      user_id: 12,
      created_at: "2026-06-24T10:00:00Z",
      expires_at: null,
      last_seen_at: "2026-06-24T10:05:00Z",
      ended_at: null
    };
    state.heartbeatMutation.isPending = false;
    state.heartbeatMutation.isError = false;
    state.heartbeatMutation.error = null;
    state.heartbeatMutation.mutate.mockReset();
    state.endMutation.isPending = false;
    state.endMutation.isError = false;
    state.endMutation.error = null;
    state.endMutation.mutate.mockReset();
  });

  it("sends a heartbeat without a client timestamp payload", async () => {
    const user = userEvent.setup();
    render(<SessionDetailPage />);

    await user.click(screen.getByRole("button", { name: "Heartbeat" }));

    expect(state.heartbeatMutation.mutate).toHaveBeenCalledWith();
  });

  it("shows the heartbeat mutation error", () => {
    state.heartbeatMutation.isError = true;
    state.heartbeatMutation.error = new Error("last_seen_at: Input should be a valid datetime");

    render(<SessionDetailPage />);

    expect(screen.getByText("last_seen_at: Input should be a valid datetime")).toBeInTheDocument();
  });
});
