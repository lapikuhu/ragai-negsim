import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StudentDetailPage } from "./StudentDetailPage";

const state = vi.hoisted(() => ({
  userQuery: {
    isLoading: false,
    isError: false,
    data: {
      id: 7,
      username: "alice",
      user_email_address: "alice@example.com" as string | null,
      roles: [{ id: 2, name: "student" }]
    },
    error: null as Error | null,
    refetch: vi.fn()
  },
  simulationsQuery: {
    isLoading: false,
    isError: false,
    data: [
      {
        id: 21,
        name: "Supplier negotiation",
        description: "Negotiate a renewal",
        status: "completed",
        user_id_owner: 1,
        user_id_participant: 7,
        corpus_id: 3,
        rag_profile_id: 4,
        teacher_reviewed: false,
        created_at: "2026-06-24T10:00:00Z",
        last_updated: "2026-06-24T10:30:00Z"
      }
    ],
    error: null as Error | null,
    refetch: vi.fn()
  }
}));

vi.mock("react-router-dom", () => ({
  useParams: () => ({ username: "alice" })
}));

vi.mock("@/features/users/userQueries", () => ({
  useUserDetailQuery: () => state.userQuery,
  useStudentSimulationsQuery: () => state.simulationsQuery
}));

describe("StudentDetailPage", () => {
  beforeEach(() => {
    state.userQuery.isLoading = false;
    state.userQuery.isError = false;
    state.userQuery.data = {
      id: 7,
      username: "alice",
      user_email_address: "alice@example.com",
      roles: [{ id: 2, name: "student" }]
    };
    state.userQuery.error = null;
    state.userQuery.refetch.mockReset();
    state.simulationsQuery.isLoading = false;
    state.simulationsQuery.isError = false;
    state.simulationsQuery.data = [
      {
        id: 21,
        name: "Supplier negotiation",
        description: "Negotiate a renewal",
        status: "completed",
        user_id_owner: 1,
        user_id_participant: 7,
        corpus_id: 3,
        rag_profile_id: 4,
        teacher_reviewed: false,
        created_at: "2026-06-24T10:00:00Z",
        last_updated: "2026-06-24T10:30:00Z"
      }
    ];
    state.simulationsQuery.error = null;
    state.simulationsQuery.refetch.mockReset();
  });

  it("shows student details and a read-only simulation list", () => {
    render(<StudentDetailPage />);

    expect(screen.getByRole("heading", { name: "alice" })).toBeInTheDocument();
    expect(screen.getByText("User ID").nextElementSibling).toHaveTextContent("7");
    expect(screen.getByText("Email").nextElementSibling).toHaveTextContent("alice@example.com");
    expect(screen.getByText("Roles").nextElementSibling).toHaveTextContent("student");
    expect(screen.getByRole("cell", { name: "Supplier negotiation" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Negotiate a renewal" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "completed" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Supplier negotiation" })).not.toBeInTheDocument();
  });

  it("shows an empty state when the student has no simulations", () => {
    state.simulationsQuery.data = [];

    render(<StudentDetailPage />);

    expect(screen.getByRole("heading", { name: "No simulations" })).toBeInTheDocument();
  });

  it("shows a fallback when the student has no email", () => {
    state.userQuery.data.user_email_address = null;

    render(<StudentDetailPage />);

    expect(screen.getByText("Email").nextElementSibling).toHaveTextContent("Not available");
  });

  it("shows a user request error before rendering the page", () => {
    state.userQuery.isError = true;
    state.userQuery.error = new Error("Student not found");

    render(<StudentDetailPage />);

    expect(screen.getByText("Student not found")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
