import { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/app/AuthProvider";
import { LoadingState } from "@/components/common/LoadingState";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { getErrorMessage } from "@/api/client";

export function LoginPage() {
  const auth = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as {
    from?: { pathname?: string; search?: string; hash?: string };
  } | null)?.from;
  const destination = `${from?.pathname ?? "/"}${from?.search ?? ""}${from?.hash ?? ""}`;

  if (auth.status === "validating") {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <LoadingState label="Checking your session..." />
      </div>
    );
  }

  if (auth.isAuthenticated) {
    return <Navigate to={destination} replace />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <div className="mb-6">
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Negotiation Simulator</p>
          <h1 className="mt-2 text-2xl font-semibold text-slate-950">Sign in</h1>
          <p className="mt-2 text-sm text-slate-600">
            Use your backend account. Login is submitted as form-encoded credentials to the existing `/users/login`
            route.
          </p>
        </div>

        <form
          className="grid gap-4"
          onSubmit={async (event) => {
            event.preventDefault();
            setError(null);
            auth.clearSessionError();
            try {
              await auth.login({ username, password });
            } catch (submitError) {
              setError(getErrorMessage(submitError, "Unable to sign in"));
            }
          }}
        >
          <Field label="Username">
            <Input value={username} onChange={(event) => setUsername(event.target.value)} required />
          </Field>

          <Field label="Password">
            <Input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </Field>

          {error || auth.sessionError ? <p className="text-sm text-red-700">{error ?? auth.sessionError}</p> : null}

          <Button type="submit" disabled={auth.isLoading}>
            {auth.isLoading ? "Signing in..." : "Sign in"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
