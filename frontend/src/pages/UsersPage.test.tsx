import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as userQueries from "@/features/users/userQueries";

import { UsersPage } from "./UsersPage";

describe("UsersPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("submits selected role ids from checkbox choices", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ ok: true });

    vi.spyOn(userQueries, "useUsersQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      refetch: vi.fn()
    } as never);
    vi.spyOn(userQueries, "useUserRolesQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        { id: 1, name: "admin" },
        { id: 2, name: "student" },
        { id: 3, name: "teacher" }
      ]
    } as never);
    vi.spyOn(userQueries, "useCreateUserMutation").mockReturnValue({
      isPending: false,
      mutateAsync
    } as never);

    render(<UsersPage />);

    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "alice" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } });
    fireEvent.click(screen.getByLabelText("student"));
    fireEvent.click(screen.getByLabelText("teacher"));
    fireEvent.click(screen.getByRole("button", { name: "Register user" }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        username: "alice",
        password: "password123",
        role_ids: [2, 3]
      });
    });
  });

  it("shows a roles loading state and keeps submit disabled until a role is selected", () => {
    vi.spyOn(userQueries, "useUsersQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
      refetch: vi.fn()
    } as never);
    vi.spyOn(userQueries, "useUserRolesQuery").mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined
    } as never);
    vi.spyOn(userQueries, "useCreateUserMutation").mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn()
    } as never);

    render(<UsersPage />);

    expect(screen.getByText("Loading roles...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Register user" })).toBeDisabled();
  });
});