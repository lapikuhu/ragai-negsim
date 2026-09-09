import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { UserDetailPage } from "./UserDetailPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <UserDetailPage />
    </MemoryRouter>
  );
}

const state = vi.hoisted(() => {
  const query = (items: unknown[]) => ({
    isLoading: false,
    isError: false,
    data: { items, hasMore: false },
    error: null as Error | null,
    refetch: vi.fn()
  });
  return ({
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
    data: { items: [
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
    ], hasMore: false },
    error: null as Error | null,
    refetch: vi.fn()
  },
  evaluationsQuery: query([]),
  scenariosQuery: query([]),
  corporaQuery: query([]),
  personasQuery: query([]),
  ragProfilesQuery: query([]),
  createdUsersQuery: query([]),
  simulationSkips: [] as number[],
  usernameParam: "alice"
  });
});

vi.mock("react-router-dom", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router-dom")>()),
  useParams: () => ({ username: state.usernameParam })
}));

vi.mock("@/features/users/userQueries", () => ({
  useUserDetailQuery: () => state.userQuery,
  useUserSimulationsQuery: (_userId: number, _enabled: boolean, skip: number) => {
    state.simulationSkips.push(skip);
    return skip > 0
      ? { ...state.simulationsQuery, data: { items: [], hasMore: false } }
      : state.simulationsQuery;
  },
  useUserEvaluationsQuery: () => state.evaluationsQuery,
  useUserScenariosQuery: () => state.scenariosQuery,
  useUserCorporaQuery: () => state.corporaQuery,
  useUserPersonasQuery: () => state.personasQuery,
  useUserRagProfilesQuery: () => state.ragProfilesQuery,
  useUsersCreatedByQuery: () => state.createdUsersQuery
}));

describe("UserDetailPage", () => {
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
    state.simulationsQuery.data = { items: [
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
    ], hasMore: false };
    state.simulationsQuery.error = null;
    state.simulationsQuery.refetch.mockReset();
    state.evaluationsQuery.data = { items: [], hasMore: false };
    state.scenariosQuery.data = { items: [], hasMore: false };
    state.corporaQuery.data = { items: [], hasMore: false };
    state.personasQuery.data = { items: [], hasMore: false };
    state.ragProfilesQuery.data = { items: [], hasMore: false };
    state.createdUsersQuery.data = { items: [], hasMore: false };
    state.simulationSkips = [];
    state.usernameParam = "alice";
  });

  it("shows student details and a read-only simulation list", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "alice" })).toBeInTheDocument();
    expect(screen.getByText("User ID").nextElementSibling).toHaveTextContent("7");
    expect(screen.getByText("Email").nextElementSibling).toHaveTextContent("alice@example.com");
    expect(screen.getByText("Roles").nextElementSibling).toHaveTextContent("student");
    expect(screen.getByRole("cell", { name: "Supplier negotiation" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Negotiate a renewal" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "completed" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Supplier negotiation" })).toHaveAttribute(
      "href",
      "/simulations/21"
    );
    expect(screen.queryByRole("heading", { name: "Evaluations given" })).not.toBeInTheDocument();
  });

  it("shows teacher activity cards and hides admin-only cards", () => {
    state.userQuery.data = {
      id: 7,
      username: "teacher-alice",
      user_email_address: "alice@example.com",
      roles: [{ id: 3, name: "teacher" }]
    };
    state.evaluationsQuery.data = { items: [{
      id: 31,
      name: "Reviewed negotiation",
      description: "Reviewed",
      status: "completed",
      teacher_reviewed: true,
      created_at: "2026-06-24T10:00:00Z",
      last_updated: "2026-06-24T10:30:00Z"
    }], hasMore: false };
    state.scenariosQuery.data = { items: [{ id: 41, name: "Vendor renewal", description: "Scenario" }], hasMore: false };
    state.corporaQuery.data = { items: [{ id: 51, name: "Procurement", description: "Corpus" }], hasMore: false };
    state.personasQuery.data = { items: [{ id: 61, name: "Firm supplier", description: "Persona" }], hasMore: false };

    renderPage();

    expect(screen.getByRole("heading", { name: "Evaluations given" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Simulations participated in" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Scenarios created" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Corpora created" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Personas created" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Reviewed negotiation" })).toHaveAttribute(
      "href",
      "/evaluations/31/review"
    );
    expect(screen.getByRole("link", { name: "Procurement" })).toHaveAttribute(
      "href",
      "/corpora/51"
    );
    expect(screen.queryByRole("link", { name: "Vendor renewal" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Firm supplier" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "RAG Profiles created" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Users created" })).not.toBeInTheDocument();
  });

  it("shows scenario titles without descriptions", () => {
    state.userQuery.data = {
      id: 7,
      username: "teacher-alice",
      user_email_address: "alice@example.com",
      roles: [{ id: 3, name: "teacher" }]
    };
    state.scenariosQuery.data = {
      items: [{ id: 41, name: "Vendor renewal", description: "Scenario details" }],
      hasMore: false
    };

    renderPage();

    const scenariosCard = screen.getByRole("heading", { name: "Scenarios created" }).closest("section");
    expect(scenariosCard).not.toBeNull();
    expect(within(scenariosCard!).getByText("Vendor renewal")).toBeInTheDocument();
    expect(within(scenariosCard!).queryByText("Scenario details")).not.toBeInTheDocument();
    expect(within(scenariosCard!).queryByRole("columnheader", { name: "Description" })).not.toBeInTheDocument();
  });

  it("shows persona titles without descriptions", () => {
    state.userQuery.data = {
      id: 7,
      username: "teacher-alice",
      user_email_address: "alice@example.com",
      roles: [{ id: 3, name: "teacher" }]
    };
    state.personasQuery.data = {
      items: [{ id: 61, name: "Firm supplier", description: "Persona details" }],
      hasMore: false
    };

    renderPage();

    const personasCard = screen.getByRole("heading", { name: "Personas created" }).closest("section");
    expect(personasCard).not.toBeNull();
    expect(within(personasCard!).getByText("Firm supplier")).toBeInTheDocument();
    expect(within(personasCard!).queryByText("Persona details")).not.toBeInTheDocument();
    expect(within(personasCard!).queryByRole("columnheader", { name: "Description" })).not.toBeInTheDocument();
  });

  it("shows admin-only RAG profiles and created users with available links", () => {
    state.userQuery.data = {
      id: 7,
      username: "admin-alice",
      user_email_address: "alice@example.com",
      roles: [{ id: 1, name: "admin" }]
    };
    state.ragProfilesQuery.data = { items: [{ id: 71, name: "Hybrid profile", strategy: "crag" }], hasMore: false };
    state.createdUsersQuery.data = { items: [{
      id: 81,
      username: "created-student",
      user_email_address: "student@example.com",
      roles: [{ id: 2, name: "student" }]
    }], hasMore: false };

    renderPage();

    expect(screen.getByRole("heading", { name: "RAG Profiles created" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Users created" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Hybrid profile" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "created-student" })).toHaveAttribute(
      "href",
      "/users/created-student"
    );
  });

  it("shows an empty state when the student has no simulations", () => {
    state.simulationsQuery.data = { items: [], hasMore: false };

    renderPage();

    expect(screen.getByRole("heading", { name: "No simulations" })).toBeInTheDocument();
  });

  it("can return from an empty next page", async () => {
    state.simulationsQuery.data = {
      items: state.simulationsQuery.data.items,
      hasMore: true
    };

    renderPage();
    await userEvent.click(screen.getByRole("button", { name: "Next simulations participated in page" }));

    expect(state.simulationSkips).toContain(20);
    await userEvent.click(screen.getByRole("button", { name: "Previous simulations participated in page" }));
    expect(state.simulationSkips.at(-1)).toBe(0);
  });

  it("resets activity pagination when navigating to another user", async () => {
    state.simulationsQuery.data = {
      items: state.simulationsQuery.data.items,
      hasMore: true
    };
    const view = renderPage();
    await userEvent.click(screen.getByRole("button", { name: "Next simulations participated in page" }));

    state.usernameParam = "bob";
    state.userQuery.data = { ...state.userQuery.data, username: "bob", id: 8 };
    view.rerender(
      <MemoryRouter>
        <UserDetailPage />
      </MemoryRouter>
    );

    expect(state.simulationSkips.at(-1)).toBe(0);
  });

  it("shows a fallback when the student has no email", () => {
    state.userQuery.data.user_email_address = null;

    renderPage();

    expect(screen.getByText("Email").nextElementSibling).toHaveTextContent("Not available");
  });

  it("shows a user request error before rendering the page", () => {
    state.userQuery.isError = true;
    state.userQuery.error = new Error("Student not found");

    renderPage();

    expect(screen.getByText("Student not found")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
