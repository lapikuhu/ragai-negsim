import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import {
  getUserByUsername,
  listUserSimulations,
  listUserCorpora,
  listUserEvaluations,
  listUserPersonas,
  listUserRagProfiles,
  listUserScenarios,
  listUsersCreatedBy
} from "./userQueries";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    apiClient: { GET: vi.fn() }
  };
});

describe("user detail requests", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads the named user and filters simulations by that user's participant id", async () => {
    const user = { id: 7, username: "alice", roles: [{ id: 2, name: "student" }] };
    vi.mocked(apiClient.GET)
      .mockResolvedValueOnce({
        data: user,
        error: undefined,
        response: new Response(null, { status: 200 })
      } as never)
      .mockResolvedValueOnce({
        data: [],
        error: undefined,
        response: new Response(null, { status: 200 })
      } as never);

    await expect(getUserByUsername("alice")).resolves.toEqual(user);
    await expect(listUserSimulations(7)).resolves.toEqual({ items: [], hasMore: false });

    expect(apiClient.GET).toHaveBeenNthCalledWith(1, "/users/{username}", {
      params: { path: { username: "alice" } }
    });
    expect(apiClient.GET).toHaveBeenNthCalledWith(2, "/simulations/", {
      params: { query: { skip: 0, limit: 21, participant_id: 7 } }
    });
  });

  it("requests each teacher and admin activity list with the viewed user id", async () => {
    vi.mocked(apiClient.GET).mockResolvedValue({
      data: [],
      error: undefined,
      response: new Response(null, { status: 200 })
    } as never);

    await listUserScenarios(7);
    await listUserCorpora(7);
    await listUserPersonas(7);
    await listUserRagProfiles(7);
    await listUsersCreatedBy(7);

    expect(apiClient.GET).toHaveBeenCalledWith("/scenarios/", {
      params: { query: { skip: 0, limit: 21, created_by_user_id: 7 } }
    });
    expect(apiClient.GET).toHaveBeenCalledWith("/corpora/", {
      params: { query: { skip: 0, limit: 21, created_by_user_id: 7 } }
    });
    expect(apiClient.GET).toHaveBeenCalledWith("/counterpart-personas/", {
      params: { query: { skip: 0, limit: 21, created_by_user_id: 7 } }
    });
    expect(apiClient.GET).toHaveBeenCalledWith("/rag-profiles/", {
      params: { query: { skip: 0, limit: 21, created_by_user_id: 7 } }
    });
    expect(apiClient.GET).toHaveBeenCalledWith("/users/", {
      params: { query: { skip: 0, limit: 21, created_by_user_id: 7 } }
    });
  });

  it("paginates evaluations assigned to the reviewing user", async () => {
    const reviewed = { id: 31, name: "Reviewed", teacher_reviewed: true };
    vi.mocked(apiClient.GET).mockResolvedValue({
      data: [reviewed],
      error: undefined,
      response: new Response(null, { status: 200 })
    } as never);

    await expect(listUserEvaluations(7)).resolves.toEqual({ items: [reviewed], hasMore: false });
    expect(apiClient.GET).toHaveBeenCalledWith("/simulations/", {
      params: { query: { skip: 0, limit: 21, teacher_id: 7 } }
    });
  });

  it("reports another page without returning the lookahead row", async () => {
    const rows = Array.from({ length: 21 }, (_, id) => ({ id, name: `Simulation ${id}` }));
    vi.mocked(apiClient.GET).mockResolvedValue({
      data: rows,
      error: undefined,
      response: new Response(null, { status: 200 })
    } as never);

    await expect(listUserSimulations(7, 40, 20)).resolves.toEqual({
      items: rows.slice(0, 20),
      hasMore: true
    });
    expect(apiClient.GET).toHaveBeenCalledWith("/simulations/", {
      params: { query: { skip: 40, limit: 21, participant_id: 7 } }
    });
  });
});
