import { Link } from "react-router-dom";

import { Card } from "@/components/ui/Card";

export function NotFoundPage() {
  return (
    <main className="mx-auto grid min-h-screen max-w-2xl place-items-center px-6 py-12">
      <Card className="w-full text-center">
        <p className="text-sm font-medium text-slate-500">404</p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-950">Page not found</h1>
        <p className="mt-3 text-sm text-slate-600">The page you requested is unavailable.</p>
        <Link
          className="mt-6 inline-flex rounded-xl bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
          to="/"
        >
          Go to dashboard
        </Link>
      </Card>
    </main>
  );
}
