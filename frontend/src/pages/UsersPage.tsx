import { useState } from "react";
import { useCreateUserMutation, useUsersQuery, useUpdateUserMutation } from "@/features/users/userQueries";
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
  const createMutation = useCreateUserMutation();
  const [form, setForm] = useState({ username: "", password: "", roles: "" });

  return (
    <div className="grid gap-6">
      <PageHeader title="Users" description="Admin user list and registration flow from `/users`." />

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Register user</h2>
        <form
          className="mt-4 grid gap-3 md:grid-cols-3"
          onSubmit={async (event) => {
            event.preventDefault();
            await createMutation.mutateAsync({
              username: form.username,
              password: form.password,
              role_ids: form.roles
                .split(",")
                .map((role) => role.trim())
                .filter(Boolean)
                .map(Number)
            });
            setForm({ username: "", password: "", roles: "" });
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
          <Field label="Role IDs" hint="Comma-separated role IDs from the seeded backend, for example `1` or `1,2`.">
            <Input value={form.roles} onChange={(event) => setForm((current) => ({ ...current, roles: event.target.value }))} />
          </Field>
          <div className="md:col-span-3">
            <Button type="submit" disabled={createMutation.isPending}>
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
