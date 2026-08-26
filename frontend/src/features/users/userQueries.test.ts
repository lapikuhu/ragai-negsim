import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import { getUserByUsername, listStudentSimulations } from "./userQueries";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    apiClient: { GET: vi.fn() }
  };
});

describe("student detail requests", () => {
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
    await expect(listStudentSimulations(7)).resolves.toEqual([]);

    expect(apiClient.GET).toHaveBeenNthCalledWith(1, "/users/{username}", {
      params: { path: { username: "alice" } }
    });
    expect(apiClient.GET).toHaveBeenNthCalledWith(2, "/simulations/", {
      params: { query: { skip: 0, limit: 50, participant_id: 7 } }
    });
  });
});
