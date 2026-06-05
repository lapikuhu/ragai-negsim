import { useAuth } from "@/app/AuthProvider";
import { Button } from "@/components/ui/Button";

export function Topbar() {
  const auth = useAuth();

  return (
    <header className="flex flex-col gap-3 rounded-2xl border border-white/70 bg-white/80 px-5 py-4 backdrop-blur md:flex-row md:items-center md:justify-between">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Signed in</p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate-700">
          <span className="font-medium text-slate-900">{auth.user?.username ?? "Unknown user"}</span>
          <span className="text-slate-400">/</span>
          <span>{(auth.user?.roles ?? []).map((role) => role.name).join(", ") || "No roles"}</span>
        </div>
      </div>
      <Button type="button" variant="secondary" onClick={auth.logout}>
        Log out
      </Button>
    </header>
  );
}
