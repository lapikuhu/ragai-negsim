import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/app/AuthProvider";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { getErrorMessage } from "@/api/client";

export function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (auth.isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const destination = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "/";

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
            try {
              await auth.login({ username, password });
              navigate(destination, { replace: true });
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

          {error ? <p className="text-sm text-red-700">{error}</p> : null}

          <Button type="submit" disabled={auth.isLoading}>
            {auth.isLoading ? "Signing in..." : "Sign in"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
