import { useState } from "react";
import { getErrorMessage } from "@/api/client";
import { useCreateUserMutation, useUserRolesQuery, useUsersQuery } from "@/features/users/userQueries";
import { PageHeader } from "@/components/common/PageHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/common/DataTable";
import { Field, Input } from "@/components/ui/Field";

export function UsersPage() {
  const query = useUsersQuery();
  const rolesQuery = useUserRolesQuery();
  const createMutation = useCreateUserMutation();
  const [form, setForm] = useState({ username: "", password: "", roleIds: [] as number[] });
  const [message, setMessage] = useState<string | null>(null);

  const toggleRole = (roleId: number) => {
    setForm((current) => ({
      ...current,
      roleIds: current.roleIds.includes(roleId)
        ? current.roleIds.filter((value) => value !== roleId)
        : [...current.roleIds, roleId]
    }));
  };

  return (
    <div className="grid gap-6">
      <PageHeader title="Users" description="Admin user list and registration flow from `/users`." />

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Register user</h2>
        <form
          className="mt-4 grid gap-3 md:grid-cols-3"
          onSubmit={async (event) => {
            event.preventDefault();
            try {
              setMessage(null);
              await createMutation.mutateAsync({
                username: form.username,
                password: form.password,
                role_ids: form.roleIds
              });
              setForm({ username: "", password: "", roleIds: [] });
            } catch (error) {
              setMessage(getErrorMessage(error, "Unable to create user"));
            }
          }}
        >
          <Field label="Username">
            <Input
              value={form.username}
              onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
              required
            />
          </Field>
          <Field label="Password">
            <Input
              type="password"
              value={form.password}
              onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
              required
            />
          </Field>
          <Field
            label="Roles"
            hint="Select one or more roles for the new user."
            error={rolesQuery.isError ? rolesQuery.error.message : undefined}
          >
            <div className="grid gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm">
              {rolesQuery.isLoading ? (
                <span className="text-slate-500">Loading roles...</span>
              ) : rolesQuery.data?.length ? (
                rolesQuery.data.map((role) => (
                  <label key={role.id} className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={form.roleIds.includes(role.id)}
                      onChange={() => toggleRole(role.id)}
                    />
                    <span className="capitalize">{role.name}</span>
                  </label>
                ))
              ) : (
                <span className="text-slate-500">No roles available.</span>
              )}
            </div>
          </Field>
          {message ? <p className="md:col-span-3 text-sm text-red-700">{message}</p> : null}
          <div className="md:col-span-3">
            <Button type="submit" disabled={createMutation.isPending || rolesQuery.isLoading || !form.roleIds.length}>
              {createMutation.isPending ? "Creating..." : "Register user"}
            </Button>
          </div>
        </form>
      </Card>

      {query.isLoading ? (
        <LoadingState label="Loading users..." />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => query.refetch()} />
      ) : query.data?.length ? (
        <DataTable
          rows={query.data}
          columns={[
            { key: "username", header: "Username", render: (user) => user.username },
            {
              key: "roles",
              header: "Roles",
              render: (user) => (user.roles ?? []).map((role) => role.name).join(", ") || "No roles"
            }
          ]}
        />
      ) : (
        <EmptyState title="No users" description="Register users once authentication is seeded." />
      )}
    </div>
  );
}
